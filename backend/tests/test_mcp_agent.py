"""MCP 与审批的联调：外部工具必须挂起，批准后才真的调用（阶段 7 T6）。

这里用**真的** stdio MCP 服务器（`tests/fixtures/mcp_echo_server.py`）走一遍
`registry_for → stream_run → approval_required → decide_approval → resume_run`，
验证的不是「适配器能连上」，而是「接进执行循环后级别仍是 external、必须经人」。
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.executor import decide_approval, prepare_run, registry_for, resume_run, stream_run
from app.agent.tools import ToolLevel
from app.auth.service import register_user
from app.llm.fake import FakeLLM, final_reply, tool_reply
from app.mcp.manager import reset_manager
from app.models import AgentApproval, AgentRun, Conversation, McpServer

FIXTURE = Path(__file__).parent / "fixtures" / "mcp_echo_server.py"


@pytest.fixture(autouse=True)
def _fresh_manager():
    """每个用例都从空连接池开始，避免上一个用例的 MCP 子进程串味。"""
    reset_manager()
    yield
    reset_manager()


def _setup(db: Session, email: str = "mcp-agent@example.com"):
    user = register_user(db, email, "password123")
    conversation = Conversation(user_id=user.id, title="MCP 联调")
    db.add(conversation)
    server = McpServer(
        user_id=user.id,
        slug="echo",
        display_name="回显测试",
        transport="stdio",
        command="uv",
        args=["run", "--no-sync", "python", str(FIXTURE)],
        enabled=True,
    )
    db.add(server)
    db.commit()
    return user, conversation, server


def _drain(events: Iterator[dict]) -> list[dict]:
    return list(events)


def test_mcp_tools_are_external_and_need_approval(db_session: Session):
    user, conversation, _ = _setup(db_session)
    registry = registry_for(db_session, user.id, conversation.id)

    names = [name for name in registry.names() if name.startswith("mcp__echo__")]
    assert names == ["mcp__echo__echo", "mcp__echo__add"]
    for name in names:
        assert registry.meta(name).level is ToolLevel.EXTERNAL
        assert registry.meta(name).requires_approval is True
        assert registry.meta(name).source == "mcp"


def test_mcp_call_suspends_then_runs_after_approval(db_session: Session):
    user, conversation, server = _setup(db_session, "mcp-approve@example.com")
    llm = FakeLLM(
        tool_script=[
            tool_reply("mcp__echo__echo", {"text": "你好，MCP"}),
            final_reply("回显结果拿到了。"),
        ]
    )
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="用回显工具说你好"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )
    assert [event["type"] for event in events] == ["run_started", "tool_call", "approval_required"]
    row = db_session.scalar(select(AgentApproval).where(AgentApproval.run_id == run.id))
    assert row is not None
    assert row.tool_name == "mcp__echo__echo"
    assert row.status == "pending"
    assert db_session.get(AgentRun, run.id).status == "waiting_approval"

    db_session.refresh(run)
    _, decided = decide_approval(
        db_session,
        user_id=user.id,
        run_id=run.id,
        approval_id=row.id,
        approved=True,
        note=None,
    )
    assert decided.status == "approved"

    resumed = _drain(
        resume_run(
            db_session,
            run=run,
            approval=decided,
            llm=llm,
            user_id=user.id,
        )
    )
    types = [event["type"] for event in resumed]
    assert types[0] == "tool_result"
    result = resumed[0]
    assert result["ok"] is True
    assert result["content"] == "你好，MCP"
    assert types[-1] == "run_finished"
    assert db_session.get(AgentRun, run.id).status == "completed"
    # 连接成功后服务器状态被回写，市场页才能显示「正常」
    db_session.refresh(server)
    assert server.last_status == "ok"


def test_rejected_mcp_call_is_fed_back_without_running(db_session: Session):
    user, conversation, _ = _setup(db_session, "mcp-reject@example.com")
    llm = FakeLLM(
        tool_script=[
            tool_reply("mcp__echo__echo", {"text": "不该被执行"}),
            final_reply("好的，不调用。"),
        ]
    )
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="试着调用"
    )
    _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )
    row = db_session.scalar(select(AgentApproval).where(AgentApproval.run_id == run.id))
    assert row is not None
    db_session.refresh(run)
    _, decided = decide_approval(
        db_session,
        user_id=user.id,
        run_id=run.id,
        approval_id=row.id,
        approved=False,
        note="先不要连外网",
    )
    resumed = _drain(
        resume_run(
            db_session, run=run, approval=decided, llm=llm, user_id=user.id, note="先不要连外网"
        )
    )
    result = resumed[0]
    assert result["type"] == "tool_result"
    assert result["ok"] is False
    assert "用户拒绝" in result["content"]
    assert "先不要连外网" in result["content"]
