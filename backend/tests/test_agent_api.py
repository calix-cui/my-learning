"""Agent 接口层测试：SSE 事件序列、前置错误、历史回放与越权。"""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.llm import get_user_llm
from app.llm.fake import FakeLLM, final_reply, tool_reply
from app.main import app


def _read_events(response) -> list[dict]:
    events: list[dict] = []
    for line in response.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode()
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _conversation(client: TestClient) -> int:
    created = client.post("/api/conversations", json={"title": "agent 测试"})
    return created.json()["data"]["id"]


@pytest.fixture()
def llm() -> Iterator[FakeLLM]:
    fake = FakeLLM(
        tool_script=[tool_reply("calculator", {"expression": "2^10"}), final_reply("1024")]
    )
    app.dependency_overrides[get_user_llm] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_user_llm, None)


def test_stream_requires_login(anon_client: TestClient):
    response = anon_client.post("/api/conversations/1/agent/stream", json={"content": "hi"})
    assert response.status_code == 401
    assert response.json()["message"] == "请先登录"


@pytest.mark.usefixtures("llm")
def test_stream_events_and_final_message(client: TestClient):
    conversation_id = _conversation(client)

    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/agent/stream",
        json={"content": "2 的 10 次方"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _read_events(response)

    types = [event["type"] for event in events]
    assert types == ["run_started", "tool_call", "tool_result", "run_finished"]
    assert events[2]["content"] == "1024"
    assert events[-1]["content"] == "1024"

    # 最终答复写进了 messages，中间步骤留在 agent_steps
    detail = client.get(f"/api/conversations/{conversation_id}").json()["data"]
    assert [item["role"] for item in detail["messages"]] == ["user", "assistant"]


@pytest.mark.usefixtures("llm")
def test_stream_rejects_blank_content(client: TestClient):
    conversation_id = _conversation(client)
    # 长度过得了 pydantic，但全是空白要在 service 层拦住，且开流前就是普通 JSON
    response = client.post(
        f"/api/conversations/{conversation_id}/agent/stream", json={"content": "   "}
    )
    assert response.status_code == 400
    assert response.json()["message"] == "消息内容不能只包含空白"


@pytest.mark.usefixtures("llm")
def test_stream_rejects_foreign_conversation(client: TestClient, anon_client: TestClient):
    conversation_id = _conversation(client)
    # 用另一个账号访问同一会话：必须 404，而不是把内容喂给它
    other = anon_client
    other.post(
        "/api/auth/register", json={"email": "agent-other@example.com", "password": "password123"}
    )
    response = other.post(
        f"/api/conversations/{conversation_id}/agent/stream", json={"content": "偷看"}
    )
    assert response.status_code == 404


@pytest.mark.usefixtures("llm")
def test_runs_list_returns_steps(client: TestClient):
    conversation_id = _conversation(client)
    with client.stream(
        "POST", f"/api/conversations/{conversation_id}/agent/stream", json={"content": "算一下"}
    ) as response:
        _read_events(response)

    payload = client.get(f"/api/conversations/{conversation_id}/agent/runs").json()["data"]
    assert len(payload["items"]) == 1
    run = payload["items"][0]
    assert run["status"] == "completed"
    assert [step["kind"] for step in run["steps"]] == [
        "user_message",
        "tool_call",
        "tool_result",
        "final_answer",
    ]
    # 工具名与参数要能回放
    assert run["steps"][1]["tool_name"] == "calculator"
    assert run["steps"][1]["tool_args"] == {"expression": "2^10"}


@pytest.mark.usefixtures("llm")
def test_runs_list_requires_ownership(client: TestClient, anon_client: TestClient):
    conversation_id = _conversation(client)
    anon_client.post(
        "/api/auth/register", json={"email": "agent-x@example.com", "password": "password123"}
    )
    response = anon_client.get(f"/api/conversations/{conversation_id}/agent/runs")
    assert response.status_code == 404


@pytest.mark.usefixtures("llm")
def test_busy_conversation_returns_409(client: TestClient, db_session):
    """同一会话同时只允许一个运行：第二个请求立刻 409，不排队烧 token。"""
    from sqlalchemy import select

    from app.agent.executor import prepare_run
    from app.models import User

    conversation_id = _conversation(client)
    user = db_session.scalar(select(User).where(User.email == "user@example.com"))
    assert user is not None
    prepare_run(db_session, user_id=user.id, conversation_id=conversation_id, content="第一次运行")

    response = client.post(
        f"/api/conversations/{conversation_id}/agent/stream", json={"content": "第二次"}
    )
    assert response.status_code == 409
    assert response.json()["message"] == "这个会话正在生成回复，请稍后再试"


def _approval_llm() -> FakeLLM:
    return FakeLLM(
        tool_script=[tool_reply("rename_conversation", {"conversation_id": 1, "title": "新名字"})]
    )


def test_write_tool_stops_at_approval_and_can_be_approved(client: TestClient):
    fake = _approval_llm()
    app.dependency_overrides[get_user_llm] = lambda: fake
    try:
        conversation_id = _conversation(client)
        # 剧本里的 conversation_id 是 1，改成刚建的会话
        fake._tool_script[0]["arguments"] = json.dumps(
            {"conversation_id": conversation_id, "title": "新名字"}
        )

        stream = client.post(
            f"/api/conversations/{conversation_id}/agent/stream", json={"content": "帮我改名"}
        )
        events = _read_events(stream)
        assert [event["type"] for event in events] == [
            "run_started",
            "tool_call",
            "approval_required",
        ]
        approval = events[-1]
        assert approval["tool"] == "rename_conversation"

        listed = client.get(f"/api/agent/runs/{approval['run_id']}/approvals")
        assert listed.json()["data"]["items"][0]["status"] == "pending"

        decided = client.post(
            f"/api/agent/runs/{approval['run_id']}/approvals/{approval['approval_id']}",
            json={"decision": "approve"},
        )
        resumed = _read_events(decided)
        assert [event["type"] for event in resumed] == ["tool_result", "run_finished"]
        assert resumed[0]["ok"] is True

        detail = client.get(f"/api/conversations/{conversation_id}").json()["data"]
        assert detail["title"] == "新名字"

        # 同一个审批不能决定两次
        again = client.post(
            f"/api/agent/runs/{approval['run_id']}/approvals/{approval['approval_id']}",
            json={"decision": "approve"},
        )
        assert again.status_code == 409
    finally:
        app.dependency_overrides.pop(get_user_llm, None)


def test_rejecting_feeds_refusal_back_and_keeps_title(client: TestClient):
    fake = _approval_llm()
    app.dependency_overrides[get_user_llm] = lambda: fake
    try:
        conversation_id = _conversation(client)
        fake._tool_script[0]["arguments"] = json.dumps(
            {"conversation_id": conversation_id, "title": "不应该生效"}
        )

        stream = client.post(
            f"/api/conversations/{conversation_id}/agent/stream", json={"content": "帮我改名"}
        )
        approval = _read_events(stream)[-1]

        decided = client.post(
            f"/api/agent/runs/{approval['run_id']}/approvals/{approval['approval_id']}",
            json={"decision": "reject", "note": "先不改"},
        )
        resumed = _read_events(decided)
        assert resumed[0]["type"] == "tool_result"
        assert resumed[0]["ok"] is False
        assert "用户拒绝" in resumed[0]["content"]

        detail = client.get(f"/api/conversations/{conversation_id}").json()["data"]
        assert detail["title"] == "agent 测试"
    finally:
        app.dependency_overrides.pop(get_user_llm, None)


def test_approvals_are_scoped_to_the_owner(client: TestClient, anon_client: TestClient):
    fake = _approval_llm()
    app.dependency_overrides[get_user_llm] = lambda: fake
    try:
        conversation_id = _conversation(client)
        fake._tool_script[0]["arguments"] = json.dumps(
            {"conversation_id": conversation_id, "title": "x"}
        )
        stream = client.post(
            f"/api/conversations/{conversation_id}/agent/stream", json={"content": "改名"}
        )
        approval = _read_events(stream)[-1]
    finally:
        app.dependency_overrides.pop(get_user_llm, None)

    assert anon_client.get(f"/api/agent/runs/{approval['run_id']}/approvals").status_code == 401

    other = TestClient(app)
    other.post(
        "/api/auth/register",
        json={"email": "intruder-agent@example.com", "password": "password123"},
    )
    # 别人的 run：一律 404，不暴露存在性
    assert other.get(f"/api/agent/runs/{approval['run_id']}/approvals").status_code == 404
