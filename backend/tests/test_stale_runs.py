"""服务重启后，上一个进程留下的运行必须被收掉，否则会话会被永久锁住。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent import executor
from app.models import AgentRun, AgentStep, Conversation, User


def _run(db: Session, user: User, conversation: Conversation, status: str) -> AgentRun:
    run = AgentRun(
        conversation_id=conversation.id,
        user_id=user.id,
        status=status,
        started_time=datetime.now(),
    )
    db.add(run)
    db.flush()
    return run


def test_startup_marks_runs_left_by_a_dead_process(
    db_session: Session, user: User, monkeypatch
):
    conversation = Conversation(user_id=user.id, title="重启前")
    db_session.add(conversation)
    db_session.flush()
    running = _run(db_session, user, conversation, "running")
    waiting = _run(db_session, user, conversation, "waiting_approval")
    done = _run(db_session, user, conversation, "completed")
    db_session.add(AgentStep(run_id=running.id, seq=1, kind="user_message", content="问题"))
    db_session.commit()
    running_id, waiting_id, done_id = running.id, waiting.id, done.id

    # 收尾用的是独立 Session，这里让它指向同一个测试库。
    monkeypatch.setattr(executor, "SessionLocal", sessionmaker(bind=db_session.get_bind()))

    assert executor.remove_stale_runs() == 1

    db_session.expire_all()
    runs = {
        run.id: run
        for run in db_session.scalars(
            select(AgentRun).where(AgentRun.id.in_([running_id, waiting_id, done_id]))
        )
    }
    assert runs[running_id].status == "failed"
    assert runs[running_id].error_message == executor.STALE_RUN_MESSAGE
    assert runs[running_id].finished_time is not None
    # 等审批的运行是「活着但暂停」，不是残留，不能被顺手清掉。
    assert runs[waiting_id].status == "waiting_approval"
    assert runs[waiting_id].finished_time is None
    assert runs[done_id].status == "completed"
