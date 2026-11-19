"""运行中心：执行在后台线程里跑，SSE 只是订阅者。

为什么要这一层：以前 `stream_run` 这个生成器**就是**执行循环，它跑在请求线程里，
连接一断（Starlette 结束响应 → `encode_sse` 关掉生成器）执行就跟着停了，用户刷新
页面等于把正在跑的那一轮掐死。

现在拆成两件事：

- 执行：`RunHub` 把任务交给一个守护线程，线程自己开 Session、自己装模型与工具；
- 观看：一次 HTTP 连接只是一个订阅者，断开只是少一个订阅者，不影响执行。

订阅者先读 `history`（已经产生、但还没人看的事件），再跟实时队列，所以「订阅晚了一点」
不会丢事件。`inline` 只给测试用：置真时任务在调用线程、用调用方会话同步跑完，行为与
改造前完全一致。
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent import events
from app.agent.executor import build_policy, registry_for, resume_run, stream_run
from app.agent.tools import ToolRegistry
from app.database import SessionLocal
from app.llm import LLMClient
from app.llm.base import LLMMessage
from app.models import AgentApproval, AgentRun, Conversation, Message
from app.services import chat_service

logger = logging.getLogger(__name__)

# 同时运行的条数上限：必须小于连接池上限（默认 5+10=15），给普通请求留余量
MAX_CONCURRENT_RUNS = 4
# 单个订阅者的待发缓冲；读得太慢就被踢掉，不能拖住执行
SUBSCRIBER_BUFFER = 256
# 订阅者回来之前已产生的事件留在这里，只用于「订阅晚了一点」的补发
HISTORY_LIMIT = 512
# 正文快照的写入节奏：攒够这么多字，或者距上次写入超过这么久，就落一次库
DRAFT_FLUSH_CHARS = 200
DRAFT_FLUSH_SECONDS = 0.5

_END: Any = None


class Subscription:
    """一次观看：先补历史，再跟实时。断开时 `close()` 注销。"""

    def __init__(self, channel: _Channel, live: queue.Queue, history: list[dict]) -> None:
        self._channel = channel
        self._live = live
        self._history = history
        self._closed = False

    def events(self) -> Iterator[dict]:
        try:
            yield from self._history
            while True:
                item = self._live.get()
                if item is _END:
                    return
                yield item
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._channel.unsubscribe(self._live)


class _Channel:
    """一次运行的事件出口：一份历史 + 若干实时订阅者。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._subscribers: list[queue.Queue] = []
        self._closed = False

    def subscribe(self) -> Subscription:
        live: queue.Queue = queue.Queue(maxsize=SUBSCRIBER_BUFFER)
        with self._lock:
            history = list(self._history)
            if self._closed:
                live.put_nowait(_END)
            else:
                self._subscribers.append(live)
        return Subscription(self, live, history)

    def unsubscribe(self, live: queue.Queue) -> None:
        with self._lock:
            if live in self._subscribers:
                self._subscribers.remove(live)

    def emit(self, event: dict) -> None:
        with self._lock:
            self._history.append(event)
            if len(self._history) > HISTORY_LIMIT:
                del self._history[: len(self._history) - HISTORY_LIMIT]
            targets = list(self._subscribers)
        for live in targets:
            if not _push(live, event):
                # 读得太慢：踢掉这个订阅者，执行不为它停
                logger.warning("订阅者落后太多，已断开", extra={"event": event.get("type")})
                self.unsubscribe(live)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            targets = list(self._subscribers)
            self._subscribers.clear()
        for live in targets:
            _push(live, _END)


def _push(live: queue.Queue, item: Any) -> bool:
    try:
        live.put_nowait(item)
    except queue.Full:
        return False
    return True


class _DraftWriter:
    """把正在生成的正文按节奏写进 `agent_runs.draft_content`。

    连接断了以后，用户重新订阅时先看到的就是这一列。写的是「当前轮」的正文：
    这一轮被写成步骤（`assistant_preview_reset`）或整个运行结束时清空。
    """

    def __init__(self, db: Session, run: AgentRun) -> None:
        self._db = db
        self._run = run
        self._text = ""
        self._last = time.monotonic()

    def append(self, piece: str) -> None:
        if not piece:
            return
        self._text += piece
        if len(piece) >= DRAFT_FLUSH_CHARS or time.monotonic() - self._last >= DRAFT_FLUSH_SECONDS:
            self.flush()

    def flush(self) -> None:
        self._write(self._text)

    def clear(self) -> None:
        if not self._text and self._run.draft_content is None:
            return
        self._text = ""
        self._write("")

    def _write(self, text: str) -> None:
        self._last = time.monotonic()
        self._run.draft_content = text or None
        self._run.draft_updated_time = datetime.now() if text else None  # noqa: DTZ005
        try:
            self._db.commit()
        except Exception:
            # 快照写失败不能影响执行：回滚后继续跑，下一次写入再试
            logger.exception("写入正文快照失败", extra={"run_id": self._run.id})
            self._db.rollback()


class RunHub:
    """运行登记处：谁在跑、谁在看。"""

    def __init__(self, max_workers: int = MAX_CONCURRENT_RUNS) -> None:
        self.max_workers = max_workers
        self._channels: dict[int, _Channel] = {}
        self._threads: set[threading.Thread] = set()
        self._lock = threading.Lock()
        self._session_factory: Callable[[], Session] = SessionLocal
        # 测试把它置真：任务同步跑完，事件全进 history，读起来与改造前一致
        self.inline = False

    # ---- 对外入口 -------------------------------------------------------

    def start_new_run(
        self, *, db: Session, run_id: int, user_id: int, llm: LLMClient
    ) -> Subscription:
        """开跑一次新运行并返回订阅。订阅先建好，避免漏掉第一批事件。"""
        channel, subscription = self._open(run_id)
        self._launch(
            run_id,
            channel,
            lambda session: self._drive_new(session, run_id, user_id, llm, channel),
            caller_db=db,
        )
        return subscription

    def start_resume(
        self,
        *,
        db: Session,
        run_id: int,
        user_id: int,
        approval_id: int,
        note: str | None,
        llm: LLMClient,
    ) -> Subscription:
        """审批后续跑：同样交给后台线程，连接断了也照样往下跑。"""
        channel, subscription = self._open(run_id)
        self._launch(
            run_id,
            channel,
            lambda session: self._drive_resume(
                session, run_id, user_id, approval_id, note, llm, channel
            ),
            caller_db=db,
        )
        return subscription

    def active_runs(self) -> int:
        with self._lock:
            return len(self._channels)

    # ---- 内部 -----------------------------------------------------------

    def _open(self, run_id: int) -> tuple[_Channel, Subscription]:
        with self._lock:
            channel = self._channels.get(run_id)
            if channel is None:
                channel = _Channel()
                self._channels[run_id] = channel
        return channel, channel.subscribe()

    def _launch(
        self,
        run_id: int,
        channel: _Channel,
        task: Callable[[Session], None],
        *,
        caller_db: Session,
    ) -> None:
        if self.inline:
            # 测试：用调用方会话同步跑，不另开连接
            self._execute(run_id, channel, task, caller_db)
            return
        thread = threading.Thread(
            target=self._thread_main,
            args=(run_id, channel, task),
            name=f"agent-run-{run_id}",
            daemon=True,
        )
        with self._lock:
            self._threads.add(thread)
        thread.start()

    def _thread_main(self, run_id: int, channel: _Channel, task: Callable[[Session], None]) -> None:
        try:
            with self._session_factory() as db:
                self._execute(run_id, channel, task, db)
        finally:
            current = threading.current_thread()
            with self._lock:
                self._threads.discard(current)

    def _execute(
        self, run_id: int, channel: _Channel, task: Callable[[Session], None], db: Session
    ) -> None:
        try:
            task(db)
        except Exception:
            # 线程里的异常没有人接，必须自己收干净：记日志 + 给用户一个终态
            logger.exception("后台运行失败", extra={"run_id": run_id})
            channel.emit(events.error(500, "运行失败，请稍后重试"))
        finally:
            channel.close()
            with self._lock:
                self._channels.pop(run_id, None)

    def _drive_new(
        self, db: Session, run_id: int, user_id: int, llm: LLMClient, channel: _Channel
    ) -> None:
        run = db.get(AgentRun, run_id)
        if run is None:
            channel.emit(events.error(404, "运行不存在"))
            return
        conversation = db.get(Conversation, run.conversation_id)
        if conversation is None:
            channel.emit(events.error(404, "会话不存在"))
            return
        registry = (
            registry_for(db, user_id, run.conversation_id)
            if getattr(llm, "supports_tool_calls", True)
            else ToolRegistry([])
        )
        self._pump(
            channel,
            stream_run(
                db,
                run=run,
                conversation=conversation,
                messages=_context(db, run.conversation_id),
                llm=llm,
                is_first_message=_is_first(db, run.conversation_id),
                user_id=user_id,
                registry=registry,
                policy=build_policy(db, user_id=user_id, registry=registry, run=run),
            ),
            db=db,
            run=run,
        )

    def _drive_resume(
        self,
        db: Session,
        run_id: int,
        user_id: int,
        approval_id: int,
        note: str | None,
        llm: LLMClient,
        channel: _Channel,
    ) -> None:
        run = db.get(AgentRun, run_id)
        approval = db.get(AgentApproval, approval_id)
        if run is None or approval is None:
            channel.emit(events.error(404, "审批不存在"))
            return
        registry = registry_for(db, user_id, run.conversation_id)
        self._pump(
            channel,
            resume_run(
                db,
                run=run,
                approval=approval,
                llm=llm,
                user_id=user_id,
                note=note,
                registry=registry,
                policy=build_policy(db, user_id=user_id, registry=registry, run=run),
            ),
            db=db,
            run=run,
        )

    @staticmethod
    def _pump(
        channel: _Channel,
        stream: Iterator[dict],
        *,
        db: Session,
        run: AgentRun,
    ) -> None:
        draft = _DraftWriter(db, run)
        try:
            for event in stream:
                channel.emit(event)
                kind = event.get("type")
                if kind == "assistant_delta":
                    draft.append(str(event.get("content") or ""))
                elif kind in {"assistant_preview_reset", "run_finished"}:
                    draft.clear()
        finally:
            # 关闭生成器，让 `stream_run` 的 finally 有机会把没跑完的运行收掉
            close = getattr(stream, "close", None)
            if close is not None:
                close()


def _context(db: Session, conversation_id: int) -> list[LLMMessage]:
    return [
        LLMMessage(role=item["role"], content=item["content"])
        for item in chat_service.build_context(db, conversation_id)
    ]


def _is_first(db: Session, conversation_id: int) -> bool:
    count = db.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    return (count or 0) <= 1


run_hub = RunHub()
