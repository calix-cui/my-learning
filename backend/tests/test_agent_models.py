"""Agent 运行/步骤两张表的约束与级联。"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.service import register_user
from app.models import AgentRun, AgentStep, Conversation


def _run(session: Session, user_id: int, conversation_id: int) -> AgentRun:
    run = AgentRun(conversation_id=conversation_id, user_id=user_id, step_count=1)
    session.add(run)
    session.flush()
    return run


def _conversation(session: Session, user_id: int) -> Conversation:
    conversation = Conversation(user_id=user_id, title="测试会话")
    session.add(conversation)
    session.flush()
    return conversation


def test_step_kind_and_payload_round_trip(db_session: Session):
    user = register_user(db_session, "agent-model@example.com", "password123")
    conversation = _conversation(db_session, user.id)
    run = _run(db_session, user.id, conversation.id)

    db_session.add(
        AgentStep(
            run_id=run.id,
            seq=1,
            kind="tool_call",
            tool_name="calculator",
            tool_args={"expression": "3**5"},
            duration_ms=12,
        )
    )
    db_session.commit()

    steps = db_session.query(AgentStep).filter_by(run_id=run.id).all()
    assert len(steps) == 1
    assert steps[0].kind == "tool_call"
    # JSON 列要能原样取回 dict，否则前端时间线拿不到参数
    assert steps[0].tool_args == {"expression": "3**5"}
    assert steps[0].duration_ms == 12
    # 关系按 seq 排序
    assert [step.seq for step in run.steps] == [1]


def test_steps_are_ordered_by_seq(db_session: Session):
    user = register_user(db_session, "agent-order@example.com", "password123")
    conversation = _conversation(db_session, user.id)
    run = _run(db_session, user.id, conversation.id)

    for seq, kind in [(2, "tool_result"), (1, "user_message"), (3, "final_answer")]:
        db_session.add(AgentStep(run_id=run.id, seq=seq, kind=kind))
    db_session.commit()

    db_session.expire_all()
    steps = db_session.query(AgentStep).filter_by(run_id=run.id).order_by(AgentStep.seq).all()
    assert [step.kind for step in steps] == ["user_message", "tool_result", "final_answer"]


def test_run_id_and_seq_are_unique(db_session: Session):
    user = register_user(db_session, "agent-unique@example.com", "password123")
    conversation = _conversation(db_session, user.id)
    run = _run(db_session, user.id, conversation.id)

    db_session.add(AgentStep(run_id=run.id, seq=1, kind="user_message"))
    db_session.commit()
    db_session.add(AgentStep(run_id=run.id, seq=1, kind="assistant_text"))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_conversation_removes_runs_and_steps(db_session: Session):
    user = register_user(db_session, "agent-cascade@example.com", "password123")
    conversation = _conversation(db_session, user.id)
    run = _run(db_session, user.id, conversation.id)
    db_session.add(AgentStep(run_id=run.id, seq=1, kind="user_message"))
    db_session.commit()

    db_session.delete(conversation)
    db_session.commit()

    assert db_session.query(AgentRun).count() == 0
    assert db_session.query(AgentStep).count() == 0


def test_deleting_user_removes_runs_and_steps(db_session: Session):
    """注销账号时不能留下孤儿运行记录。"""
    user = register_user(db_session, "agent-user-cascade@example.com", "password123")
    conversation = _conversation(db_session, user.id)
    run = _run(db_session, user.id, conversation.id)
    db_session.add(AgentStep(run_id=run.id, seq=1, kind="user_message"))
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(AgentRun).count() == 0
    assert db_session.query(AgentStep).count() == 0
