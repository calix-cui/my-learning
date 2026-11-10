"""Agent 执行器：模型 ↔ 工具的往返循环（阶段 5）+ 审批暂停/恢复（阶段 6）。

形状（见 `docs/agent.md` §3.1、`docs/tools.md` §3.4）：
    user_message → [模型 → tool_calls? → 策略 → 执行/审批 → tool_result]* → final_answer

几条硬规矩：
1. **预算写死**：最多 `MAX_STEPS` 步、单工具 `TOOL_TIMEOUT_SECONDS` 超时、
   同一工具连续失败 `MAX_CONSECUTIVE_FAILURES` 次就中止。不靠提示词自觉。
2. **每步先落库再产出事件**：断流/进程挂了也能看到已经发生的步骤。
3. **最终答复才写 `messages`**：中间的工具往返属于运行过程，留在 `agent_steps`。
4. **失败也留痕**：run 标 `failed` 并写 `error_message`，不静默吞掉。
5. **审批不阻塞进程**：需要审批时把 run 标成 `waiting_approval` 并结束生成器，
   客户端决定后再从库里重放上下文继续——所以重放必须只依赖 `agent_steps`。
"""

import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent import events
from app.agent import policy as policy_module
from app.agent.tools import ToolRegistry, build_registry
from app.common.exceptions import BusinessError
from app.llm import LLMClient, LLMError
from app.llm.base import LLMMessage, ToolCall
from app.models import AgentApproval, AgentRun, AgentStep, Conversation, Message, UserSettings
from app.models.agent_approval import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
)
from app.models.agent_run import RUN_COMPLETED, RUN_FAILED, RUN_RUNNING, RUN_WAITING_APPROVAL
from app.models.agent_step import (
    STEP_ASSISTANT_TEXT,
    STEP_FINAL_ANSWER,
    STEP_TOOL_CALL,
    STEP_TOOL_RESULT,
    STEP_USER_MESSAGE,
)
from app.services import chat_service

logger = logging.getLogger(__name__)

MAX_STEPS = 8
TOOL_TIMEOUT_SECONDS = 2.0
MAX_CONSECUTIVE_FAILURES = 3

# 工具都是本地的只读实现，正常远快于 2s；这里只防「意外卡住」而不是做并发调度
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-tool")


@dataclass
class LoopState:
    """一轮循环的可变状态：暂停时要把它们带出生成器。"""

    seq: int = 1
    failures: dict[str, int] = field(default_factory=dict)
    suspended: bool = False
    finished: bool = False


def prepare_run(
    db: Session, *, user_id: int, conversation_id: int, content: str
) -> tuple[Conversation, AgentRun, list[LLMMessage], bool]:
    """开流前的准备：校验、建 run、记第一步。错误以普通异常抛出（接口层转 JSON）。"""
    conversation = chat_service.get_conversation(db, user_id, conversation_id)
    text = content.strip()
    if not text:
        raise BusinessError("消息内容不能只包含空白")

    running = db.scalar(
        select(AgentRun.id).where(
            AgentRun.conversation_id == conversation_id,
            AgentRun.status.in_((RUN_RUNNING, RUN_WAITING_APPROVAL)),
        )
    )
    if running is not None:
        raise BusinessError("这个会话正在生成回复，请稍后再试", code=409)

    message_count = db.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    is_first_message = (message_count or 0) == 0

    # 与项目其他表一致：存 naive 本地时间（全库统一，不在这里单独引入时区）
    now = datetime.now()  # noqa: DTZ005
    run = AgentRun(conversation_id=conversation_id, user_id=user_id, started_time=now)
    db.add(run)
    db.flush()
    _add_step(db, run, seq=1, kind=STEP_USER_MESSAGE, content=text)

    user_message = Message(conversation_id=conversation_id, role="user", content=text)
    db.add(user_message)
    db.flush()

    context: list[LLMMessage] = [
        LLMMessage(role=item["role"], content=item["content"])
        for item in chat_service.build_context(db, conversation_id)
    ]
    db.commit()
    return conversation, run, context, is_first_message


def stream_run(
    db: Session,
    *,
    run: AgentRun,
    conversation: Conversation,
    messages: list[LLMMessage],
    llm: LLMClient,
    is_first_message: bool,
    user_id: int,
    registry: ToolRegistry | None = None,
    policy: policy_module.ToolPolicy | None = None,
) -> Iterator[dict]:
    """跑循环并逐个产出事件。生成器被关闭（客户端断流）时把 run 标成 cancelled。"""
    tools = registry or registry_for(db, user_id, conversation.id)
    tool_policy = policy or build_policy(db, user_id=user_id, registry=tools, run=run)

    yield events.run_started(run.id, conversation.id)
    yield from _run_loop(
        db,
        run=run,
        conversation=conversation,
        messages=messages,
        llm=llm,
        is_first_message=is_first_message,
        user_id=user_id,
        tools=tools,
        policy=tool_policy,
        state=LoopState(seq=_last_seq(db, run)),
    )


def resume_run(
    db: Session,
    *,
    run: AgentRun,
    approval: AgentApproval,
    llm: LLMClient,
    user_id: int,
    note: str | None = None,
    registry: ToolRegistry | None = None,
    policy: policy_module.ToolPolicy | None = None,
) -> Iterator[dict]:
    """用户做出决定后继续跑：重放上下文 → 补上这次调用的结果 → 接着循环。"""
    conversation = chat_service.get_conversation(db, user_id, run.conversation_id)
    tools = registry or registry_for(db, user_id, conversation.id)
    tool_policy = policy or build_policy(db, user_id=user_id, registry=tools, run=run)
    messages, pending = _replay_messages(db, run)
    state = LoopState(seq=_last_seq(db, run))

    call: ToolCall = {
        "id": f"call_{pending.seq if pending else approval.seq}",
        "name": approval.tool_name,
        "arguments": json.dumps(approval.tool_args or {}, ensure_ascii=False),
    }

    if approval.status == APPROVAL_REJECTED:
        reason = note or approval.note or "未说明理由"
        content = f"用户拒绝执行 {approval.tool_name}：{reason}"
        result = {"ok": False, "content": content, "duration_ms": 0, "args": approval.tool_args}
    else:
        result = _execute(tools, call, user_id=user_id)
        tool_policy.daily_used += 1

    if pending is not None:
        # 补回「模型要调用这个工具」的那条 assistant 消息，tool 消息必须紧跟着它
        messages.append(
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {"name": call["name"], "arguments": call["arguments"]},
                    }
                ],
            )
        )

    state.seq += 1
    _add_step(
        db,
        run,
        seq=state.seq,
        kind=STEP_TOOL_RESULT,
        content=result["content"][:2000],
        tool_name=approval.tool_name,
        tool_args=result["args"],
        ok=result["ok"],
        duration_ms=result["duration_ms"],
    )
    messages.append(LLMMessage(role="tool", content=result["content"], tool_call_id=call["id"]))
    db.commit()
    yield events.tool_result(
        state.seq,
        approval.tool_name,
        result["ok"],
        result["content"][:2000],
        result["duration_ms"],
    )

    if not result["ok"]:
        state.failures[approval.tool_name] = state.failures.get(approval.tool_name, 0) + 1

    yield from _run_loop(
        db,
        run=run,
        conversation=conversation,
        messages=messages,
        llm=llm,
        is_first_message=_is_first_message(db, conversation.id),
        user_id=user_id,
        tools=tools,
        policy=tool_policy,
        state=state,
    )


def _run_loop(
    db: Session,
    *,
    run: AgentRun,
    conversation: Conversation,
    messages: list[LLMMessage],
    llm: LLMClient,
    is_first_message: bool,
    user_id: int,
    tools: ToolRegistry,
    policy: policy_module.ToolPolicy,
    state: LoopState,
) -> Iterator[dict]:
    """真正的循环体：`stream_run` 与 `resume_run` 共用。"""
    specs = tools.specs()
    # 每轮重新确认状态：恢复时 run 还是 waiting_approval，要先改回 running
    run.status = RUN_RUNNING
    db.commit()

    try:
        for _ in range(MAX_STEPS):
            try:
                reply = llm.chat_with_tools(messages, specs)
            except LLMError as exc:
                _fail(db, run, str(exc))
                yield events.error(exc.code, str(exc))
                return

            if reply["model"]:
                run.model = reply["model"]

            calls = reply["tool_calls"]

            # 只有「说完话接着调工具」才算 Thought；没有工具调用时这段文本就是最终答复，
            # 不能既记一条 assistant_text 又记一条 final_answer（内容会重复一遍）
            if reply["content"] and calls:
                state.seq += 1
                _add_step(
                    db, run, seq=state.seq, kind=STEP_ASSISTANT_TEXT, content=reply["content"]
                )
                db.commit()
                yield events.assistant_text(state.seq, reply["content"])

            if not calls:
                final = (reply["content"] or "").strip()
                if not final:
                    _fail(db, run, "模型没有给出答复")
                    yield events.error(502, "模型没有给出答复")
                    return

                state.seq += 1
                _add_step(db, run, seq=state.seq, kind=STEP_FINAL_ANSWER, content=final)
                _save_final_message(
                    db,
                    conversation=conversation,
                    content=final,
                    model=reply["model"],
                    is_first_message=is_first_message,
                    title_source=last_user_text(messages),
                )
                run.status = RUN_COMPLETED
                run.finished_time = datetime.now()  # noqa: DTZ005
                run.step_count = state.seq
                db.commit()
                state.finished = True
                yield events.run_finished(run.id, final, state.seq, run.model)
                return

            messages.append(
                LLMMessage(
                    role="assistant",
                    content=reply["content"] or "",
                    tool_calls=[
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["name"], "arguments": call["arguments"]},
                        }
                        for call in calls
                    ],
                )
            )

            for call in calls:
                state.seq += 1
                _add_step(
                    db,
                    run,
                    seq=state.seq,
                    kind=STEP_TOOL_CALL,
                    tool_name=call["name"],
                    content=None,
                    # 参数在这里先落一份（模型给的原始 JSON），前端时间线可以「先看到要调什么」
                    tool_args=_safe_json(call["arguments"]),
                )
                db.commit()
                yield events.tool_call(state.seq, call["name"], _safe_json(call["arguments"]))

                decision = policy.check(call["name"], _safe_json(call["arguments"]))

                if decision.needs_approval:
                    approval = _open_approval(
                        db,
                        run=run,
                        user_id=user_id,
                        seq=state.seq,
                        call=call,
                        reason=decision.reason,
                    )
                    state.suspended = True
                    yield events.approval_required(
                        run.id,
                        approval.id,
                        state.seq,
                        call["name"],
                        _safe_json(call["arguments"]),
                        decision.reason,
                    )
                    return

                if decision.action == "deny":
                    if decision.fatal:
                        _fail(db, run, decision.reason)
                        yield events.error(403, decision.reason)
                        return
                    result = _denied(decision.reason)
                else:
                    result = _execute(tools, call, user_id=user_id)
                    policy.daily_used += 1

                state.seq += 1
                _add_step(
                    db,
                    run,
                    seq=state.seq,
                    kind=STEP_TOOL_RESULT,
                    content=result["content"][:2000],
                    tool_name=call["name"],
                    tool_args=result["args"],
                    ok=result["ok"],
                    duration_ms=result["duration_ms"],
                )
                db.commit()
                yield events.tool_result(
                    state.seq,
                    call["name"],
                    result["ok"],
                    result["content"][:2000],
                    result["duration_ms"],
                )

                messages.append(
                    LLMMessage(
                        role="tool",
                        content=result["content"],
                        tool_call_id=call["id"],
                    )
                )

                if not result["ok"]:
                    state.failures[call["name"]] = state.failures.get(call["name"], 0) + 1
                    if state.failures[call["name"]] >= MAX_CONSECUTIVE_FAILURES:
                        message = (
                            f"工具 {call['name']} 连续失败 {MAX_CONSECUTIVE_FAILURES} 次，已中止"
                        )
                        _fail(db, run, message)
                        yield events.error(500, message)
                        return

        # 走完预算还没收尾：明确失败，而不是继续烧
        message = f"超过最大步数（{MAX_STEPS} 步），已中止"
        _fail(db, run, message)
        yield events.error(500, message)
    finally:
        if not state.finished and not state.suspended and run.status == RUN_RUNNING:
            # 客户端断开或生成器被提前关闭：不要在库里留下永远 running 的运行
            try:
                _fail(db, run, "运行被中断")
            except Exception:
                logger.exception("标记 agent 运行中断失败")


def registry_for(db: Session, user_id: int, conversation_id: int | None = None) -> ToolRegistry:
    """按账号设置装配注册表：被关掉的工具既不展示也执行不了。"""
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    disabled = tuple(row.tools_disabled or []) if row is not None else ()
    return build_registry(db, disabled=disabled, conversation_id=conversation_id)


def build_policy(
    db: Session,
    *,
    user_id: int,
    registry: ToolRegistry,
    run: AgentRun | None = None,
) -> policy_module.ToolPolicy:
    """把用户设置、当日用量与本次运行的历史审批拼成一份策略。"""
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    disabled = frozenset(row.tools_disabled or []) if row is not None else frozenset()
    budget = row.daily_tool_budget if row is not None else policy_module.DEFAULT_DAILY_TOOL_BUDGET

    today = datetime.now().date()  # noqa: DTZ005
    daily_used = db.scalar(
        select(func.count(AgentStep.id))
        .join(AgentRun, AgentRun.id == AgentStep.run_id)
        .where(
            AgentRun.user_id == user_id,
            AgentStep.kind == STEP_TOOL_CALL,
            func.date(AgentStep.create_time) == today,
        )
    )
    approvals_used = 0
    rejects: dict[str, int] = {}
    if run is not None:
        approvals_used = (
            db.scalar(select(func.count(AgentApproval.id)).where(AgentApproval.run_id == run.id))
            or 0
        )
        for tool_name, count in db.execute(
            select(AgentApproval.tool_name, func.count(AgentApproval.id))
            .where(AgentApproval.run_id == run.id, AgentApproval.status == APPROVAL_REJECTED)
            .group_by(AgentApproval.tool_name)
        ):
            rejects[tool_name] = count

    return policy_module.ToolPolicy(
        registry=registry,
        disabled=disabled,
        daily_budget=int(budget or policy_module.DEFAULT_DAILY_TOOL_BUDGET),
        daily_used=int(daily_used or 0),
        approvals_used=int(approvals_used),
        rejects_by_tool=rejects,
    )


def decide_approval(
    db: Session,
    *,
    user_id: int,
    run_id: int,
    approval_id: int,
    approved: bool,
    note: str | None,
) -> tuple[AgentRun, AgentApproval]:
    """记录决定。只改状态，真正执行交给 `resume_run`（同一个请求内继续流式返回）。"""
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id))
    if run is None:
        raise BusinessError("运行不存在", code=404)
    approval = db.scalar(
        select(AgentApproval).where(
            AgentApproval.id == approval_id,
            AgentApproval.run_id == run.id,
            AgentApproval.user_id == user_id,
        )
    )
    if approval is None:
        raise BusinessError("审批不存在", code=404)
    if approval.status != APPROVAL_PENDING:
        raise BusinessError("这次审批已经处理过了", code=409)
    if run.status != RUN_WAITING_APPROVAL:
        raise BusinessError("这个运行不在等待审批的状态", code=409)

    approval.status = APPROVAL_APPROVED if approved else APPROVAL_REJECTED
    approval.note = (note or "")[:255] or None
    approval.decided_time = datetime.now()  # noqa: DTZ005
    db.commit()
    return run, approval


def _open_approval(
    db: Session,
    *,
    run: AgentRun,
    user_id: int,
    seq: int,
    call: ToolCall,
    reason: str,
) -> AgentApproval:
    approval = AgentApproval(
        run_id=run.id,
        user_id=user_id,
        seq=seq,
        tool_name=call["name"],
        tool_args=_safe_json(call["arguments"]),
        status=APPROVAL_PENDING,
        note=reason[:255] or None,
    )
    db.add(approval)
    run.status = RUN_WAITING_APPROVAL
    run.step_count = seq
    db.commit()
    db.refresh(approval)
    return approval


def _replay_messages(db: Session, run: AgentRun) -> tuple[list[LLMMessage], AgentStep | None]:
    """从 `agent_steps` 重放上下文。tool_call 与 tool_result 按顺序配对。

    返回 (messages, pending)：`pending` 是最后那次「已记录调用、还没有结果」的步骤，
    也就是审批挂起的那一次，由 `resume_run` 补上 assistant + tool 消息。
    """
    steps = list(
        db.scalars(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.seq))
    )
    messages: list[LLMMessage] = []
    pending: AgentStep | None = None

    for step in steps:
        if step.kind == STEP_USER_MESSAGE:
            pending = None
            messages.append(LLMMessage(role="user", content=step.content or ""))
        elif step.kind == STEP_ASSISTANT_TEXT or step.kind == STEP_FINAL_ANSWER:
            pending = None
            messages.append(LLMMessage(role="assistant", content=step.content or ""))
        elif step.kind == STEP_TOOL_CALL:
            pending = step
        elif step.kind == STEP_TOOL_RESULT and pending is not None:
            call_id = f"call_{pending.seq}"
            messages.append(
                LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": pending.tool_name or "",
                                "arguments": json.dumps(
                                    pending.tool_args or {}, ensure_ascii=False
                                ),
                            },
                        }
                    ],
                )
            )
            messages.append(
                LLMMessage(role="tool", content=step.content or "", tool_call_id=call_id)
            )
            pending = None

    return messages, pending


def _execute(tools: ToolRegistry, call: ToolCall, *, user_id: int):
    """执行单个工具，带超时。超时也返回结果，让模型知道发生了什么。"""
    future = _pool.submit(tools.execute, call["name"], call["arguments"], user_id=user_id)
    try:
        return future.result(timeout=TOOL_TIMEOUT_SECONDS)
    except FutureTimeoutError:
        future.cancel()
        return {
            "ok": False,
            "content": f"工具执行超过 {TOOL_TIMEOUT_SECONDS:g} 秒，已放弃",
            "duration_ms": int(TOOL_TIMEOUT_SECONDS * 1000),
            "args": None,
            "error": "timeout",
        }


def _denied(reason: str) -> dict[str, Any]:
    """策略拒绝：不执行工具，把理由原样回灌给模型，让它自己换路子。"""
    return {
        "ok": False,
        "content": f"拒绝执行：{reason}",
        "duration_ms": 0,
        "args": None,
        "error": "denied",
    }


def _last_seq(db: Session, run: AgentRun) -> int:
    value = db.scalar(select(func.max(AgentStep.seq)).where(AgentStep.run_id == run.id))
    return int(value or 1)


def _is_first_message(db: Session, conversation_id: int) -> bool:
    count = db.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    return (count or 0) == 0


def _add_step(
    db: Session,
    run: AgentRun,
    *,
    seq: int,
    kind: str,
    content: str | None = None,
    tool_name: str | None = None,
    tool_args: dict | None = None,
    ok: bool | None = None,
    duration_ms: int | None = None,
) -> AgentStep:
    step = AgentStep(
        run_id=run.id,
        seq=seq,
        kind=kind,
        content=content,
        tool_name=tool_name,
        tool_args=tool_args,
        ok=ok,
        duration_ms=duration_ms,
    )
    db.add(step)
    return step


def last_user_text(messages: list[LLMMessage]) -> str:
    """上下文里最后一条用户消息——会话标题用它，而不是助手答复。"""
    for message in reversed(messages):
        if message["role"] == "user" and message.get("content"):
            return str(message["content"])
    return ""


def _save_final_message(
    db: Session,
    *,
    conversation: Conversation,
    content: str,
    model: str | None,
    is_first_message: bool,
    title_source: str,
) -> None:
    db.add(Message(conversation_id=conversation.id, role="assistant", content=content, model=model))
    conversation.update_time = datetime.now()  # noqa: DTZ005
    if is_first_message:
        conversation.title = (
            title_source[: chat_service.TITLE_MAX_LENGTH]
            or content[: chat_service.TITLE_MAX_LENGTH]
        )


def _fail(db: Session, run: AgentRun, message: str) -> None:
    """把 run 标失败并落库；本身不能抛错，否则会掩盖真正的失败原因。"""
    try:
        db.rollback()
        run.status = RUN_FAILED
        run.error_message = message[:255]
        run.finished_time = datetime.now()  # noqa: DTZ005
        db.add(run)
        db.commit()
    except Exception:
        logger.exception("标记 agent 运行失败时出错")
        db.rollback()


def _safe_json(raw: str) -> dict | None:
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


__all__ = [
    "MAX_CONSECUTIVE_FAILURES",
    "MAX_STEPS",
    "TOOL_TIMEOUT_SECONDS",
    "build_policy",
    "decide_approval",
    "prepare_run",
    "registry_for",
    "resume_run",
    "stream_run",
]
