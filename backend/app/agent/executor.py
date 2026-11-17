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
   客户端决定后再从库里重放上下文继续——所以重放依赖持久化步骤与 Skill 快照。
"""

import json
import logging
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.agent import events
from app.agent import policy as policy_module
from app.agent.tools import BuiltinSource, ToolRegistry, ToolSource
from app.common.dev_trace import trace, trace_context, trace_enabled
from app.common.exceptions import BusinessError
from app.llm import LLMClient, LLMError
from app.llm.base import LLMMessage, ToolCall, ToolSpec
from app.mcp.errors import McpError
from app.mcp.manager import get_manager
from app.models import (
    AgentApproval,
    AgentRun,
    AgentStep,
    Conversation,
    McpServer,
    Message,
    UserSettings,
)
from app.models.agent_approval import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
)
from app.models.agent_run import RUN_COMPLETED, RUN_FAILED, RUN_RUNNING, RUN_WAITING_APPROVAL
from app.models.agent_step import (
    STEP_ASSISTANT_TEXT,
    STEP_FINAL_ANSWER,
    STEP_SKILL_LOAD_FAILED,
    STEP_SKILL_LOADED,
    STEP_TOOL_CALL,
    STEP_TOOL_RESULT,
    STEP_USER_MESSAGE,
)
from app.models.mcp_server import STATUS_ERROR, STATUS_OK
from app.services import chat_service, mcp_service, skill_service
from app.skills.models import LoadedSkill, SkillDescriptor, build_runtime_skill_prompt
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

MAX_STEPS = 8
TOOL_TIMEOUT_SECONDS = 2.0
MAX_CONSECUTIVE_FAILURES = 3
MAX_SKILL_CATALOG = 50
MAX_SKILLS_PER_RUN = 3
MAX_SKILL_INSTRUCTIONS_CHARS = 12_000
SKILL_LOAD_TOOL_NAME = "__runtime_request_skill_load"
SKILL_RESOURCE_TOOL_NAME = "__runtime_read_skill_resource"
MAX_RESOURCE_CONTEXT_BYTES = 32_768
MAX_RESOURCES_PER_RUN = 8

# 工具都是本地的只读实现，正常远快于 2s；这里只防「意外卡住」而不是做并发调度
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-tool")


@dataclass
class LoopState:
    """一轮循环的可变状态：暂停时要把它们带出生成器。"""

    seq: int = 1
    failures: dict[str, int] = field(default_factory=dict)
    skill_catalog: list[SkillDescriptor] = field(default_factory=list)
    loaded_skills: list[LoadedSkill] = field(default_factory=list)
    skill_mode: str = "manual"
    suspended: bool = False
    finished: bool = False


def prepare_run(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    content: str,
    skill_mode: str = "manual",
) -> tuple[Conversation, AgentRun, list[LLMMessage], bool]:
    """开流前的准备：校验、建 run、记第一步。错误以普通异常抛出（接口层转 JSON）。"""
    conversation = chat_service.get_conversation(db, user_id, conversation_id)
    text = content.strip()
    if not text:
        raise BusinessError("消息内容不能只包含空白")
    if skill_mode not in {"off", "manual", "auto"}:
        raise BusinessError("Skill 使用方式无效")

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
    catalog: list[SkillDescriptor] = []
    if skill_mode == "auto" or (skill_mode == "manual" and conversation.skill_slug):
        discovered = skill_service.registry_for(db, user_id).discover()
        if skill_mode == "auto":
            mounted = next(
                (item for item in discovered if item.slug == conversation.skill_slug), None
            )
            catalog = ([mounted] if mounted is not None else []) + [
                item for item in discovered if item is not mounted
            ][: MAX_SKILL_CATALOG - (1 if mounted is not None else 0)]
        elif conversation.skill_slug:
            selected = next(
                (item for item in discovered if item.slug == conversation.skill_slug), None
            )
            catalog = [selected] if selected is not None else []

    run = AgentRun(
        conversation_id=conversation_id,
        user_id=user_id,
        started_time=now,
        skill_mode=skill_mode,
        skill_snapshot=_snapshot_payload(catalog, []),
    )
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
    trace_context(
        "agent.prepare",
        context,
        run_id=run.id,
        conversation_id=conversation_id,
        skill_mode=skill_mode,
        catalog_count=len(catalog),
        first_message=is_first_message,
    )
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
    tools = registry or registry_for(db, user_id, conversation.id, skill_mode=run.skill_mode)
    tool_policy = policy or build_policy(db, user_id=user_id, registry=tools, run=run)
    state = _loop_state(db, run)
    skill_registry = skill_service.registry_for(db, user_id)

    trace("agent.start", run_id=run.id, conversation_id=conversation.id, skill_mode=run.skill_mode)
    yield events.run_started(run.id, conversation.id)
    if run.skill_mode in {"manual", "auto"} and conversation.skill_slug and not state.loaded_skills:
        descriptor = next(
            (item for item in state.skill_catalog if item.slug == conversation.skill_slug), None
        )
        key = descriptor.key if descriptor is not None else f"missing:{conversation.skill_slug}"
        _, event = _load_skill(
            db,
            run=run,
            state=state,
            registry=skill_registry,
            key=key,
        )
        trace("agent.skill.mounted", run_id=run.id, seq=state.seq, result=event["type"])
        yield event
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
        state=state,
        skill_registry=skill_registry,
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
    if (
        run.skill_mode == "manual"
        and conversation.skill_slug
        and not isinstance(run.skill_snapshot, dict)
    ):
        _fail(db, run, "本次运行缺少 Skill 版本快照，已停止恢复执行")
        yield events.error(409, "本次运行缺少 Skill 快照，请重新发起任务")
        return
    base_tools = registry or registry_for(db, user_id, conversation.id, skill_mode="off")
    state = _loop_state(db, run)
    tools = _tools_for_skills(base_tools, state.loaded_skills)
    tool_policy = policy or build_policy(db, user_id=user_id, registry=tools, run=run)
    tool_policy.registry = tools
    skill_registry = skill_service.registry_for(db, user_id)
    messages, pending = _replay_messages(db, run)
    trace_context(
        "agent.approval.replay",
        messages,
        run_id=run.id,
        approval_id=approval.id,
        status=approval.status,
        pending_step=pending.seq if pending else None,
        loaded_skills=len(state.loaded_skills),
    )
    if approval.status not in {APPROVAL_APPROVED, APPROVAL_REJECTED}:
        _fail(db, run, "审批状态无效，已拒绝恢复执行")
        yield events.error(409, "审批状态无效，无法继续此运行")
        return
    if (
        pending is None
        or pending.seq != approval.seq
        or pending.tool_name != approval.tool_name
        or pending.tool_args != approval.tool_args
    ):
        _fail(db, run, "审批与待恢复的工具调用不匹配")
        yield events.error(409, "审批记录与待执行的工具调用不匹配，已停止运行")
        return
    current_fingerprint = base_tools.fingerprint(approval.tool_name)
    if approval.status == APPROVAL_APPROVED and (
        approval.tool_fingerprint is None or current_fingerprint != approval.tool_fingerprint
    ):
        _fail(db, run, "审批后的工具定义发生变化，已拒绝执行")
        yield events.error(409, "工具定义在审批后发生变化，请重新发起任务")
        return
    messages = _messages_with_runtime_skills(messages, state, tools, run_id=run.id)

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
        # 该待审批调用已计入当日 tool_call 数；恢复检查时先扣回本次，再按授权复核。
        tool_policy.daily_used = max(0, tool_policy.daily_used - 1)
        decision = tool_policy.check(
            approval.tool_name,
            approval.tool_args,
            approval_granted=True,
        )
        trace(
            "agent.approval.policy",
            run_id=run.id,
            approval_id=approval.id,
            tool=approval.tool_name,
            action=decision.action,
            fatal=decision.fatal,
        )
        if decision.action == "deny":
            result = _denied(decision.reason)
            if decision.fatal:
                _fail(db, run, decision.reason)
                yield events.error(403, decision.reason)
                return
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
    trace(
        "agent.approval.result",
        run_id=run.id,
        approval_id=approval.id,
        seq=state.seq,
        tool=approval.tool_name,
        ok=result["ok"],
        duration_ms=result["duration_ms"],
    )
    yield events.tool_result(
        state.seq,
        approval.tool_name,
        result["ok"],
        result["content"][:2000],
        result["duration_ms"],
    )

    if result.get("error") == "timeout_uncertain":
        message = "工具执行超时且状态未知，已停止本次运行以避免重复执行"
        _fail(db, run, message)
        yield events.error(504, message)
        return

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
        tools=base_tools,
        policy=tool_policy,
        state=state,
        skill_registry=skill_registry,
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
    skill_registry: SkillRegistry,
) -> Iterator[dict]:
    """真正的循环体：`stream_run` 与 `resume_run` 共用。"""
    base_tools = tools
    # 每轮重新确认状态：恢复时 run 还是 waiting_approval，要先改回 running
    run.status = RUN_RUNNING
    db.commit()

    try:
        for round_number in range(1, MAX_STEPS + 1):
            # 每轮按已加载的 Skill 收窄工具集合，模型和执行策略使用同一注册表。
            tools = _tools_for_skills(base_tools, state.loaded_skills)
            policy.registry = tools
            specs = tools.specs()
            loaded_keys = {item.descriptor.key for item in state.loaded_skills}
            skill_control_enabled = (
                run.skill_mode == "auto"
                and any(item.key not in loaded_keys for item in state.skill_catalog)
                and SKILL_LOAD_TOOL_NAME not in tools.names()
            )
            # Skill 控制动作复用函数调用格式，由执行器单独处理。
            if skill_control_enabled:
                specs.append(_skill_load_tool_spec())
            if any(item.resources for item in state.loaded_skills):
                specs.append(_skill_resource_tool_spec())
            round_messages = _messages_with_runtime_skills(messages, state, tools, run_id=run.id)
            if trace_enabled():
                trace_context(
                    "agent.model.request",
                    round_messages,
                    run_id=run.id,
                    round=round_number,
                    seq=state.seq,
                    tools=[spec["name"] for spec in specs],
                    loaded_skills=len(state.loaded_skills),
                )
            started = time.perf_counter()
            try:
                reply = llm.chat_with_tools(round_messages, specs)
            except LLMError as exc:
                trace(
                    "agent.model.error",
                    run_id=run.id,
                    round=round_number,
                    code=exc.code,
                    error_type=type(exc).__name__,
                )
                _fail(db, run, str(exc))
                yield events.error(exc.code, str(exc))
                return

            if reply["model"]:
                run.model = reply["model"]

            calls = reply["tool_calls"]
            if trace_enabled():
                trace(
                    "agent.model.response",
                    run_id=run.id,
                    round=round_number,
                    model=reply["model"],
                    finish_reason=reply["finish_reason"],
                    chars=len(reply["content"] or ""),
                    duration_ms=round((time.perf_counter() - started) * 1000),
                    calls=[
                        {
                            "tool": call["name"],
                            "id": call["id"],
                            "argument_chars": len(call["arguments"]),
                        }
                        for call in calls
                    ],
                )

            # 只有「说完话接着调工具」才算 Thought；没有工具调用时这段文本就是最终答复，
            # 不能既记一条 assistant_text 又记一条 final_answer（内容会重复一遍）
            if reply["content"] and calls:
                state.seq += 1
                _add_step(
                    db, run, seq=state.seq, kind=STEP_ASSISTANT_TEXT, content=reply["content"]
                )
                db.commit()
                yield events.assistant_text(state.seq, reply["content"])

            # 模型没有继续请求工具时，将这轮文本作为最终答复保存。
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
                trace("agent.finish", run_id=run.id, seq=state.seq, chars=len(final))
                yield events.run_finished(run.id, final, state.seq, run.model)
                return

            # 保留模型的调用消息，下一轮按调用 ID 将它与工具结果配对。
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

            if any(
                call["name"] in {SKILL_LOAD_TOOL_NAME, SKILL_RESOURCE_TOOL_NAME} for call in calls
            ):
                # 加载指引或读取资源会改变下一轮上下文，同批普通工具暂缓执行。
                for call in calls:
                    trace(
                        "agent.skill.dispatch",
                        run_id=run.id,
                        round=round_number,
                        call_id=call["id"],
                        tool=call["name"],
                    )
                    if call["name"] == SKILL_RESOURCE_TOOL_NAME:
                        event = _read_skill_resource(
                            db, run, state, skill_registry, call["arguments"]
                        )
                        trace("agent.skill.resource", run_id=run.id, seq=state.seq, ok=event["ok"])
                        yield event
                        messages.append(
                            LLMMessage(
                                role="tool", content=event["message"], tool_call_id=call["id"]
                            )
                        )
                        continue
                    if call["name"] == SKILL_LOAD_TOOL_NAME:
                        args = _safe_json(call["arguments"]) or {}
                        key = args.get("skill_key")
                        key = key if isinstance(key, str) else ""
                        loaded, event = _load_skill(
                            db,
                            run=run,
                            state=state,
                            registry=skill_registry,
                            key=key,
                            model_requested=True,
                        )
                        trace(
                            "agent.skill.load",
                            run_id=run.id,
                            seq=state.seq,
                            result=event["type"],
                            error_code=event.get("error_code"),
                        )
                        yield event
                        observation = (
                            f"Skill 已加载：{loaded.descriptor.name}。请阅读指引后重新规划。"
                            if loaded is not None
                            else str(event.get("message", "Skill 加载失败"))
                        )
                        messages.append(
                            LLMMessage(role="tool", content=observation, tool_call_id=call["id"])
                        )
                        continue

                    state.seq += 1
                    args = _safe_json(call["arguments"])
                    _add_step(
                        db,
                        run,
                        seq=state.seq,
                        kind=STEP_TOOL_CALL,
                        tool_name=call["name"],
                        tool_args=args,
                    )
                    db.commit()
                    yield events.tool_call(state.seq, call["name"], args)
                    deferred = "本轮同时请求 Skill 指引或资源，此工具未执行；请读取后重新规划"
                    state.seq += 1
                    _add_step(
                        db,
                        run,
                        seq=state.seq,
                        kind=STEP_TOOL_RESULT,
                        content=deferred,
                        tool_name=call["name"],
                        tool_args=args,
                        ok=False,
                        duration_ms=0,
                    )
                    db.commit()
                    yield events.tool_result(state.seq, call["name"], False, deferred, 0)
                    messages.append(
                        LLMMessage(role="tool", content=deferred, tool_call_id=call["id"])
                    )
                continue

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

                # 模型提出请求，后端决定放行、拒绝或等待用户审批。
                decision = policy.check(call["name"], _safe_json(call["arguments"]))
                trace(
                    "agent.tool.policy",
                    run_id=run.id,
                    round=round_number,
                    seq=state.seq,
                    tool=call["name"],
                    call_id=call["id"],
                    action=decision.action,
                    fatal=decision.fatal,
                )

                if decision.needs_approval:
                    # 保存待审批请求并结束当前流，用户决定后从运行记录恢复。
                    approval = _open_approval(
                        db,
                        run=run,
                        user_id=user_id,
                        seq=state.seq,
                        call=call,
                        reason=decision.reason,
                        tool_fingerprint=tools.fingerprint(call["name"]),
                    )
                    state.suspended = True
                    trace(
                        "agent.approval.wait", run_id=run.id, approval_id=approval.id, seq=state.seq
                    )
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
                    trace(
                        "agent.tool.execute",
                        run_id=run.id,
                        seq=state.seq,
                        call_id=call["id"],
                        tool=call["name"],
                    )
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
                trace(
                    "agent.tool.result",
                    run_id=run.id,
                    round=round_number,
                    seq=state.seq,
                    tool=call["name"],
                    call_id=call["id"],
                    ok=result["ok"],
                    duration_ms=result["duration_ms"],
                    chars=len(result["content"]),
                    timeout=result.get("error") in ("timeout_uncertain", "timeout_cancelled"),
                )
                yield events.tool_result(
                    state.seq,
                    call["name"],
                    result["ok"],
                    result["content"][:2000],
                    result["duration_ms"],
                )

                if result.get("error") == "timeout_uncertain":
                    message = "工具执行超时且状态未知，已停止本次运行以避免重复执行"
                    _fail(db, run, message)
                    yield events.error(504, message)
                    return

                # SSE 和运行步骤只记录摘要，模型下一轮收到完整结果并按调用 ID 配对。
                messages.append(
                    LLMMessage(
                        role="tool",
                        content=result["content"],
                        tool_call_id=call["id"],
                    )
                )

                trace(
                    "agent.context.tool_added",
                    run_id=run.id,
                    round=round_number,
                    call_id=call["id"],
                    message_count=len(messages),
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


def _snapshot_descriptor(item: SkillDescriptor) -> dict[str, Any]:
    return {
        "key": item.key,
        "slug": item.slug,
        "name": item.name,
        "description": item.description,
        "source": item.source,
        "trust": item.trust,
        "version": item.version,
        "tools": list(item.tools),
        "icon": item.icon,
        "skill_id": item.skill_id,
    }


def _restore_descriptor(raw: Any) -> SkillDescriptor | None:
    if not isinstance(raw, dict):
        return None
    required = ("key", "slug", "name", "description", "source", "trust", "version")
    if any(not isinstance(raw.get(key), str) for key in required):
        return None
    tools = raw.get("tools")
    return SkillDescriptor(
        key=raw["key"],
        slug=raw["slug"],
        name=raw["name"],
        description=raw["description"],
        source=raw["source"],
        trust=raw["trust"],
        version=raw["version"],
        tools=tuple(item for item in tools if isinstance(item, str))
        if isinstance(tools, list)
        else (),
        icon=raw.get("icon") if isinstance(raw.get("icon"), str) else "sparkle",
        skill_id=raw.get("skill_id") if isinstance(raw.get("skill_id"), int) else None,
    )


def _snapshot_payload(catalog: list[SkillDescriptor], loaded: list[LoadedSkill]) -> dict[str, Any]:
    return {
        "catalog": [_snapshot_descriptor(item) for item in catalog],
        "loaded": [
            {
                "descriptor": _snapshot_descriptor(item.descriptor),
                "instructions": item.instructions,
                "content_hash": item.content_hash,
                "resources": list(item.resources),
                "resource_contents": dict(item.resource_contents),
            }
            for item in loaded
        ],
    }


def _loop_state(db: Session, run: AgentRun) -> LoopState:
    raw = run.skill_snapshot if isinstance(run.skill_snapshot, dict) else {}
    catalog = [
        item
        for raw_item in raw.get("catalog", [])
        if (item := _restore_descriptor(raw_item)) is not None
    ]
    loaded: list[LoadedSkill] = []
    for raw_item in raw.get("loaded", []):
        if not isinstance(raw_item, dict) or not isinstance(raw_item.get("instructions"), str):
            continue
        descriptor = _restore_descriptor(raw_item.get("descriptor"))
        if descriptor is None:
            continue
        instructions = raw_item["instructions"]
        if len(instructions) > MAX_SKILL_INSTRUCTIONS_CHARS:
            continue
        resources = raw_item.get("resources")
        loaded.append(
            LoadedSkill(
                descriptor=descriptor,
                instructions=instructions,
                content_hash=str(raw_item.get("content_hash") or ""),
                resource_contents=raw_item.get("resource_contents", {}),
                resources=tuple(item for item in resources if isinstance(item, str))
                if isinstance(resources, list)
                else (),
            )
        )
    return LoopState(
        seq=_last_seq(db, run),
        skill_catalog=catalog[:MAX_SKILL_CATALOG],
        loaded_skills=loaded[:MAX_SKILLS_PER_RUN],
        skill_mode=run.skill_mode or "manual",
    )


def _record_skill_failure(
    db: Session,
    run: AgentRun,
    state: LoopState,
    *,
    key: str,
    code: str,
    message: str,
    model_requested: bool = False,
) -> dict:
    state.seq += 1
    _add_step(
        db,
        run,
        seq=state.seq,
        kind=STEP_SKILL_LOAD_FAILED,
        content=message,
        tool_name=SKILL_LOAD_TOOL_NAME if model_requested else None,
        tool_args={"skill_key": key[:128]} if model_requested else None,
        skill_key=key[:128] or None,
    )
    run.step_count = state.seq
    db.commit()
    return events.skill_load_failed(state.seq, key=key[:128], error_code=code, message=message)


def _load_skill(
    db: Session,
    *,
    run: AgentRun,
    state: LoopState,
    registry: SkillRegistry,
    key: str,
    model_requested: bool = False,
) -> tuple[LoadedSkill | None, dict]:
    key = key[:128]
    expected = next((item for item in state.skill_catalog if item.key == key), None)
    if expected is None:
        message = "目录中没有这个 Skill，模型可以选择其他 Skill 或直接回答"
        return None, _record_skill_failure(
            db,
            run,
            state,
            key=key,
            code="unknown_skill",
            message=message,
            model_requested=model_requested,
        )
    if any(item.descriptor.key == key for item in state.loaded_skills):
        message = "这个 Skill 已加载，无需重复加载"
        return None, _record_skill_failure(
            db,
            run,
            state,
            key=key,
            code="already_loaded",
            message=message,
            model_requested=model_requested,
        )
    if len(state.loaded_skills) >= MAX_SKILLS_PER_RUN:
        message = f"本次最多加载 {MAX_SKILLS_PER_RUN} 个 Skill，请使用已加载内容继续"
        return None, _record_skill_failure(
            db,
            run,
            state,
            key=key,
            code="skill_limit",
            message=message,
            model_requested=model_requested,
        )

    try:
        loaded = registry.load(key)
    except Exception:
        logger.exception("加载 Skill 失败：%s", key)
        loaded = None
    if loaded is None:
        message = "Skill 当前不可用，请选择其他 Skill 或直接回答"
        return None, _record_skill_failure(
            db,
            run,
            state,
            key=key,
            code="unavailable",
            message=message,
            model_requested=model_requested,
        )
    if loaded.descriptor.version != expected.version:
        message = "Skill 内容已更新，请重新发起任务以使用新版本"
        return None, _record_skill_failure(
            db,
            run,
            state,
            key=key,
            code="version_changed",
            message=message,
            model_requested=model_requested,
        )
    total_chars = sum(len(item.instructions) for item in state.loaded_skills) + len(
        loaded.instructions
    )
    if total_chars > MAX_SKILL_INSTRUCTIONS_CHARS:
        message = "Skill 指引总长度超过本次运行限制，请选择更精简的 Skill"
        return None, _record_skill_failure(
            db,
            run,
            state,
            key=key,
            code="context_limit",
            message=message,
            model_requested=model_requested,
        )

    state.loaded_skills.append(loaded)
    run.skill_snapshot = _snapshot_payload(state.skill_catalog, state.loaded_skills)
    state.seq += 1
    observation = f"Skill 已加载：{loaded.descriptor.name}。请阅读指引后重新规划。"
    _add_step(
        db,
        run,
        seq=state.seq,
        kind=STEP_SKILL_LOADED,
        content=observation if model_requested else None,
        tool_name=SKILL_LOAD_TOOL_NAME if model_requested else None,
        tool_args={"skill_key": loaded.descriptor.key} if model_requested else None,
        skill_key=loaded.descriptor.key,
        skill_name=loaded.descriptor.name,
        skill_source=loaded.descriptor.source,
        skill_version=loaded.descriptor.version,
    )
    run.step_count = state.seq
    db.commit()
    return loaded, events.skill_loaded(
        state.seq,
        key=loaded.descriptor.key,
        name=loaded.descriptor.name,
        source=loaded.descriptor.source,
        version=loaded.descriptor.version,
    )


def _tools_for_skills(tools: ToolRegistry, skills: list[LoadedSkill]) -> ToolRegistry:
    restrictions = [set(item.descriptor.tools) for item in skills if item.descriptor.tools]
    if not restrictions:
        return tools
    allowed = set.intersection(*restrictions)
    return tools.only(allowed)


def _skill_resource_tool_spec() -> ToolSpec:
    return ToolSpec(
        name=SKILL_RESOURCE_TOOL_NAME,
        description="读取已加载 Skill 清单中的文本资源。仅提供参考内容，不执行脚本或授予权限。",
        parameters={
            "type": "object",
            "properties": {
                "skill_key": {"type": "string", "maxLength": 128},
                "path": {"type": "string", "maxLength": 240},
            },
            "required": ["skill_key", "path"],
            "additionalProperties": False,
        },
    )


def _read_skill_resource(
    db: Session, run: AgentRun, state: LoopState, registry: SkillRegistry, arguments: str
) -> dict:
    from app.skills.resources import SkillResourceError

    args = _safe_json(arguments)
    key, path = "", ""
    loaded = None
    ok = False
    try:
        if (
            not isinstance(args, dict)
            or set(args) != {"skill_key", "path"}
            or not isinstance(args["skill_key"], str)
            or not isinstance(args["path"], str)
            or len(args["skill_key"]) > 128
            or len(args["path"]) > 240
        ):
            raise SkillResourceError("资源请求参数无效")
        key, path = args["skill_key"], args["path"]
        loaded = next((item for item in state.loaded_skills if item.descriptor.key == key), None)
        if loaded is None or state.skill_mode == "off":
            raise SkillResourceError("只能读取本次已加载 Skill 的资源")
        if path not in loaded.resource_contents:
            count = sum(len(item.resource_contents) for item in state.loaded_skills)
            if count >= MAX_RESOURCES_PER_RUN:
                raise SkillResourceError("本次已达到资源数量上限")
            content = registry.read_resource(loaded, path)
            size = sum(
                len(value.encode("utf-8"))
                for item in state.loaded_skills
                for value in item.resource_contents.values()
            ) + len(content.encode("utf-8"))
            if size > MAX_RESOURCE_CONTEXT_BYTES:
                raise SkillResourceError("资源总内容超过本次运行限制")
            updated = replace(loaded, resource_contents={**loaded.resource_contents, path: content})
            state.loaded_skills[state.loaded_skills.index(loaded)] = updated
            run.skill_snapshot = _snapshot_payload(state.skill_catalog, state.loaded_skills)
        ok = True
        message = f"已读取参考资料：{path}"
    except SkillResourceError as exc:
        message = str(exc)
    except Exception:
        logger.exception("Skill 资源读取失败")
        message = "资源当前不可用，请使用已有指引继续"
    state.seq += 1
    name = loaded.descriptor.name if loaded else None
    _add_step(
        db,
        run,
        seq=state.seq,
        kind="skill_resource",
        content=message,
        tool_name=SKILL_RESOURCE_TOOL_NAME,
        tool_args={"skill_key": key, "path": path},
        skill_key=key or None,
        skill_name=name,
        ok=ok,
    )
    run.step_count = state.seq
    db.commit()
    return events.skill_resource(state.seq, key=key, name=name, path=path, ok=ok, message=message)


def _skill_load_tool_spec() -> ToolSpec:
    return ToolSpec(
        name=SKILL_LOAD_TOOL_NAME,
        description="按目录 key 加载一个相关 Skill 的完整工作指引。Skill 只提供指引，不授予工具权限。",
        parameters={
            "type": "object",
            "properties": {
                "skill_key": {"type": "string", "description": "可选 Skill 目录中的稳定 key"}
            },
            "required": ["skill_key"],
            "additionalProperties": False,
        },
    )


def _messages_with_runtime_skills(
    messages: list[LLMMessage], state: LoopState, tools: ToolRegistry, *, run_id: int
) -> list[LLMMessage]:
    loaded_keys = {item.descriptor.key for item in state.loaded_skills}
    catalog = (
        [item for item in state.skill_catalog if item.key not in loaded_keys]
        if state.skill_mode == "auto"
        else []
    )
    prompt = build_runtime_skill_prompt(
        state.loaded_skills,
        tool_names=tools.enabled_names(),
        catalog=catalog,
    )
    trace(
        "agent.prompt.compose",
        run_id=run_id,
        inserted=bool(prompt),
        chars=len(prompt or ""),
        loaded_skills=len(state.loaded_skills),
        available_skills=len(catalog),
    )
    return [LLMMessage(role="system", content=prompt), *messages] if prompt else messages


def registry_for(
    db: Session,
    user_id: int,
    conversation_id: int | None = None,
    *,
    skill_mode: str = "manual",
) -> ToolRegistry:
    """按账号设置装配注册表：内置工具 + 用户启用的 MCP 服务器。

    MCP 连不上**不能**让整次对话失败：记一行 last_status/last_error、跳过这台服务器，
    模型继续用剩下的工具回答。用户下次在设置页能看到失败原因。
    """
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    disabled = tuple(row.tools_disabled or []) if row is not None else ()

    # 汇总内置工具和当前用户启用的 MCP 工具，再应用账号的禁用名单。
    sources: list[ToolSource] = [BuiltinSource(db, conversation_id)]
    manager = get_manager()
    servers = db.scalars(
        select(McpServer).where(McpServer.user_id == user_id, McpServer.enabled.is_(True))
    )
    for server in servers:
        try:
            spec = mcp_service.spec_of_row(server)
            source = manager.source_for(server, env=spec.env)
        except McpError as exc:
            server.last_status = STATUS_ERROR
            server.last_error = str(exc)[:255]
            logger.warning("MCP 服务器 %s 不可用：%s", server.slug, exc)
            continue
        except Exception:  # pragma: no cover - 兜底：任何异常都不该打断对话
            server.last_status = STATUS_ERROR
            server.last_error = "连接失败"
            logger.exception("MCP 服务器 %s 连接异常", server.slug)
            continue
        server.last_status = STATUS_OK
        server.last_error = None
        server.tool_count = source.tool_count
        server.last_connected_time = datetime.now()  # noqa: DTZ005
        sources.append(source)
    db.flush()

    registry = ToolRegistry.from_sources(sources, disabled=disabled)
    # 兼容既有手动挂载：只依据元数据做能力收窄，不读取正文。
    if conversation_id is not None and skill_mode == "manual":
        conversation = db.get(Conversation, conversation_id)
        descriptor = (
            skill_service.describe_skill(db, user_id, conversation.skill_slug)
            if conversation is not None and conversation.skill_slug
            else None
        )
        if descriptor is not None and descriptor.tools:
            registry = registry.only(descriptor.tools)
    if trace_enabled():
        trace(
            "agent.tools.registry",
            conversation_id=conversation_id,
            skill_mode=skill_mode,
            source_count=len(sources),
            tools=registry.enabled_names(),
        )
    return registry


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

    result = db.execute(
        update(AgentApproval)
        .where(
            AgentApproval.id == approval.id,
            AgentApproval.run_id == run.id,
            AgentApproval.user_id == user_id,
            AgentApproval.status == APPROVAL_PENDING,
            AgentApproval.run.has(AgentRun.status == RUN_WAITING_APPROVAL),
        )
        .values(
            status=APPROVAL_APPROVED if approved else APPROVAL_REJECTED,
            note=(note or "")[:255] or None,
            decided_time=datetime.now(),  # noqa: DTZ005
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise BusinessError("这次审批已被处理或运行状态已变化", code=409)
    db.commit()
    db.refresh(approval)
    return run, approval


def _open_approval(
    db: Session,
    *,
    run: AgentRun,
    user_id: int,
    seq: int,
    call: ToolCall,
    reason: str,
    tool_fingerprint: str | None,
) -> AgentApproval:
    approval = AgentApproval(
        run_id=run.id,
        user_id=user_id,
        seq=seq,
        tool_name=call["name"],
        tool_args=_safe_json(call["arguments"]),
        tool_fingerprint=tool_fingerprint,
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
        elif step.kind in {
            STEP_SKILL_LOADED,
            STEP_SKILL_LOAD_FAILED,
            "skill_resource",
        } and step.tool_name in {SKILL_LOAD_TOOL_NAME, SKILL_RESOURCE_TOOL_NAME}:
            # Runtime Skill control calls are persisted as one completed step so replay can
            # restore the required assistant/tool message pair after an approval pause.
            call_id = f"call_skill_{step.seq}"
            messages.append(
                LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": step.tool_name,
                                "arguments": json.dumps(step.tool_args or {}, ensure_ascii=False),
                            },
                        }
                    ],
                )
            )
            messages.append(
                LLMMessage(role="tool", content=step.content or "", tool_call_id=call_id)
            )
            pending = None
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
    """执行单个工具，带超时。超时也返回结果，让模型知道发生了什么。

    超时按工具自己声明的 `timeout_seconds` 走：内置工具 2 秒，MCP 这类外部工具
    要等子进程与网络，给到 10 秒（T-26）。
    """
    meta = tools.meta(call["name"])
    timeout = meta.timeout_seconds if meta is not None else TOOL_TIMEOUT_SECONDS
    future = _pool.submit(tools.execute, call["name"], call["arguments"], user_id=user_id)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        cancelled = future.cancel()
        state = "任务尚未开始，已取消" if cancelled else "执行仍可能在后台继续，状态未知"
        return {
            "ok": False,
            "content": f"工具执行超过 {timeout:g} 秒；{state}",
            "duration_ms": int(timeout * 1000),
            "args": None,
            "error": "timeout_cancelled" if cancelled else "timeout_uncertain",
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
    skill_key: str | None = None,
    skill_name: str | None = None,
    skill_source: str | None = None,
    skill_version: str | None = None,
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
        skill_key=skill_key,
        skill_name=skill_name,
        skill_source=skill_source,
        skill_version=skill_version,
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
        trace("agent.fail", run_id=run.id, status=run.status)
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
