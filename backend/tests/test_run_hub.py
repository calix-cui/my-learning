"""运行中心的单元测试：订阅只是观看，不影响执行。

这些用例不碰数据库：`_execute` 拿到的 session 用空壳顶替，重点是「谁在跑、谁在看」
以及断开的订阅者会不会把执行带走。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

from app.agent import hub as hub_module
from app.agent.hub import RunHub, _DraftWriter
from app.models import AgentRun, Conversation


class _NullSession:
    def close(self) -> None:  # pragma: no cover - 只为对齐 Session 生命周期
        return None


@contextmanager
def _null_session() -> Iterator[_NullSession]:
    yield _NullSession()


def test_subscriber_that_joins_late_still_sees_earlier_events() -> None:
    hub = RunHub()
    channel, first = hub._open(7)
    first.close()  # 第一个订阅者什么都没读就退了
    channel.emit({"type": "run_started", "run_id": 7})
    channel.emit({"type": "assistant_delta", "delta": "你"})

    late = channel.subscribe()
    channel.emit({"type": "run_finished", "status": "completed"})
    channel.close()

    assert [event["type"] for event in late.events()] == [
        "run_started",
        "assistant_delta",
        "run_finished",
    ]


def test_subscriber_leaving_does_not_stop_the_run() -> None:
    hub = RunHub()
    channel, subscription = hub._open(11)
    seen: list[dict] = []
    finished = threading.Event()

    def task(_db: _NullSession) -> None:
        for index in range(3):
            channel.emit({"type": "assistant_delta", "delta": str(index)})
            time.sleep(0.01)
        finished.set()

    thread = threading.Thread(target=lambda: hub._execute(11, channel, task, _NullSession()))
    thread.start()

    # 读一个事件就断开订阅，模拟用户刷新页面
    first = subscription.events()
    seen.append(next(first))
    subscription.close()
    thread.join(timeout=5)

    assert finished.is_set(), "订阅者走后执行应继续跑完"
    assert seen == [{"type": "assistant_delta", "delta": "0"}]
    assert hub.active_runs() == 0


def test_slow_subscriber_is_dropped_instead_of_blocking_the_run(monkeypatch) -> None:
    monkeypatch.setattr(hub_module, "SUBSCRIBER_BUFFER", 1)
    hub = RunHub()
    channel, subscription = hub._open(3)
    # 一个不读的订阅者：缓冲塞满之后应当被踢掉，而不是让 emit 卡住
    for index in range(5):
        channel.emit({"type": "assistant_delta", "delta": str(index)})

    assert channel._subscribers == []
    subscription.close()


def test_inline_mode_finishes_before_returning() -> None:
    hub = RunHub()
    hub.inline = True
    hub._session_factory = _null_session  # type: ignore[assignment]
    events = []

    def task(_db: _NullSession) -> None:
        events.append("ran")

    channel, subscription = hub._open(5)
    hub._launch(5, channel, task, caller_db=_NullSession())  # type: ignore[arg-type]

    assert events == ["ran"]  # 同步跑完，返回时已经执行
    assert list(subscription.events()) == []


def test_draft_snapshot_is_flushed_while_generating(db_session, user) -> None:
    conversation = Conversation(user_id=user.id, title="快照")
    db_session.add(conversation)
    db_session.flush()
    run = AgentRun(conversation_id=conversation.id, user_id=user.id)
    db_session.add(run)
    db_session.commit()

    writer = _DraftWriter(db_session, run)
    writer.append("短")
    assert run.draft_content is None, "没攒够就不会写库"

    writer.append("x" * hub_module.DRAFT_FLUSH_CHARS)
    db_session.refresh(run)
    assert run.draft_content is not None
    assert run.draft_content.startswith("短")
    assert run.draft_updated_time is not None

    writer.clear()
    db_session.refresh(run)
    assert run.draft_content is None
