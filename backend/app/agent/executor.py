"""Agent 执行器：模型 ↔ 工具的往返循环（阶段 5 的核心）。

形状（见 `docs/agent.md` §3.1）：
    user_message → [模型 → tool_calls? → 执行 → tool_result]* → final_answer

几条硬规矩：
1. **预算写死**：最多 `MAX_STEPS` 步、单工具 `TOOL_TIMEOUT_SECONDS` 超时、
   同一工具连续失败 `MAX_CONSECUTIVE_FAILURES` 次就中止。不靠提示词自觉。
2. **每步先落库再产出事件**：断流/进程挂了也能看到已经发生的步骤。
3. **最终答复才写 `messages`**：中间的工具往返属于运行过程，留在 `agent_steps`。
4. **失败也留痕**：run 标 `failed` 并写 `error_message`，不静默吞掉。
"""

import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent import events
from app.agent.tools import ToolRegistry, build_registry
from app.llm import LLMClient, LLMError
from app.llm.base import LLMMessage, ToolCall
from app.models import AgentRun, AgentStep, Conversation, Message
from app.models.agent_run import RUN_COMPLETED, RUN_FAILED
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


def prepare_run(
    db: Session, *, user_id: int, conversation_id: int, content: str
) -> tuple[Conversation, AgentRun, list[LLMMessage], bool]:
    """开流前的准备：校验、建 run、记第一步。错误以普通异常抛出（接口层转 JSON）。"""
    conversation = chat_service.get_conversation(db, user_id, conversation_id)
    text = content.strip()
    if not text:
        raise ValueError("empty")

    running = db.scalar(
        select(AgentRun.id).where(
            AgentRun.conversation_id == conversation_id, AgentRun.status == "running"
        )
    )
    if running is not None:
        raise RuntimeError("busy")

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
) -> Iterator[dict]:
    """跑循环并逐个产出事件。生成器被关闭（客户端断流）时把 run 标成 cancelled。"""
    tools = registry or build_registry(db)
    specs = tools.specs()
    seq = 1  # 用户消息已经占掉第 1 步
    finished = False

    yield events.run_started(run.id, conversation.id)

    # 同一个工具的连续失败次数要跨轮累计，否则「一直失败」永远触发不了中止
    failures: dict[str, int] = {}

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
                seq += 1
                _add_step(db, run, seq=seq, kind=STEP_ASSISTANT_TEXT, content=reply["content"])
                db.commit()
                yield events.assistant_text(seq, reply["content"])

            if not calls:
                final = (reply["content"] or "").strip()
                if not final:
                    _fail(db, run, "模型没有给出答复")
                    yield events.error(502, "模型没有给出答复")
                    return

                seq += 1
                _add_step(db, run, seq=seq, kind=STEP_FINAL_ANSWER, content=final)
                _save_final_message(
                    db,
                    conversation=conversation,
                    content=final,
                    model=reply["model"],
                    is_first_message=is_first_message,
                )
                run.status = RUN_COMPLETED
                run.finished_time = datetime.now()  # noqa: DTZ005
                run.step_count = seq
                db.commit()
                finished = True
                yield events.run_finished(run.id, final, seq, run.model)
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
                seq += 1
                _add_step(
                    db,
                    run,
                    seq=seq,
                    kind=STEP_TOOL_CALL,
                    tool_name=call["name"],
                    content=None,
                )
                db.commit()
                yield events.tool_call(seq, call["name"], _safe_json(call["arguments"]))

                result = _execute(tools, call, user_id=user_id)

                seq += 1
                _add_step(
                    db,
                    run,
                    seq=seq,
                    kind=STEP_TOOL_RESULT,
                    content=result["content"][:2000],
                    tool_name=call["name"],
                    tool_args=result["args"],
                    ok=result["ok"],
                    duration_ms=result["duration_ms"],
                )
                db.commit()
                yield events.tool_result(
                    seq, call["name"], result["ok"], result["content"][:2000], result["duration_ms"]
                )

                messages.append(
                    LLMMessage(
                        role="tool",
                        content=result["content"],
                        tool_call_id=call["id"],
                    )
                )

                if not result["ok"]:
                    failures[call["name"]] = failures.get(call["name"], 0) + 1
                    if failures[call["name"]] >= MAX_CONSECUTIVE_FAILURES:
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
        if not finished and run.status == "running":
            # 客户端断开或生成器被提前关闭：不要在库里留下永远 running 的运行
            try:
                _fail(db, run, "运行被中断")
            except Exception:
                logger.exception("标记 agent 运行中断失败")


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


def _save_final_message(
    db: Session,
    *,
    conversation: Conversation,
    content: str,
    model: str | None,
    is_first_message: bool,
) -> None:
    db.add(Message(conversation_id=conversation.id, role="assistant", content=content, model=model))
    conversation.update_time = datetime.now()  # noqa: DTZ005
    if is_first_message:
        conversation.title = content[: chat_service.TITLE_MAX_LENGTH]


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
    import json

    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


__all__ = [
    "MAX_CONSECUTIVE_FAILURES",
    "MAX_STEPS",
    "TOOL_TIMEOUT_SECONDS",
    "prepare_run",
    "stream_run",
]
