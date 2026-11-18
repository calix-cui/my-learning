"""验证旧运行清理的边界，防止误删消息与活跃执行。"""

import importlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentApproval, AgentRun, AgentStep, Conversation, Message, User


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_cleanup_removes_only_unlinked_finished_runs(db_session: Session, user: User, status: str):
    conversation = Conversation(user_id=user.id, title="保留消息")
    db_session.add(conversation)
    db_session.flush()
    messages = [
        Message(conversation_id=conversation.id, role=role, content="保留正文")
        for role in ("user", "assistant")
    ]
    db_session.add_all(messages)
    db_session.flush()
    cases = [
        (status, None, None),
        ("completed", messages[0].id, messages[1].id),
        ("failed", messages[0].id, None),
        ("completed", None, messages[1].id),
        ("running", None, None),
        ("waiting_approval", None, None),
    ]
    run_ids = []
    for state, user_id, assistant_id in cases:
        run = AgentRun(
            conversation_id=conversation.id,
            user_id=user.id,
            status=state,
            user_message_id=user_id,
            assistant_message_id=assistant_id,
        )
        # 两条保留记录共用助手消息会触发唯一约束，分别验证每一种关联。
        if state == "completed" and user_id is None and assistant_id is not None:
            extra = Message(conversation_id=conversation.id, role="assistant", content="另一条回复")
            db_session.add(extra)
            db_session.flush()
            run.assistant_message_id = extra.id
        db_session.add(run)
        db_session.flush()
        run_ids.append(run.id)
        db_session.add(AgentStep(run_id=run.id, seq=1, kind="tool_call", tool_name="clock"))
        db_session.add(AgentApproval(run_id=run.id, user_id=user.id, seq=1, tool_name="clock"))
    db_session.flush()
    original_message_ids = list(db_session.scalars(select(Message.id)))
    migration = importlib.import_module(
        "migrations.versions.20261118_b72e80d193ac_remove_unlinked_runs"
    )
    with Operations.context(MigrationContext.configure(db_session.connection())):
        migration.upgrade()
        # 重复执行不会扩大清理范围。
        migration.upgrade()
    db_session.expire_all()
    assert list(db_session.scalars(select(AgentRun.id).order_by(AgentRun.id))) == run_ids[1:]
    for model in (AgentStep, AgentApproval):
        assert list(db_session.scalars(select(model.run_id).order_by(model.run_id))) == run_ids[1:]
    assert list(db_session.scalars(select(Message.id))) == original_message_ids
    assert db_session.get(Conversation, conversation.id) is not None
