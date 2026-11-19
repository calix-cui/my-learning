"""Agent 接口层测试：SSE 事件序列、前置错误、历史回放与越权。"""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent.hub import run_hub
from app.llm import get_user_llm
from app.llm.fake import FakeLLM, final_reply, tool_reply
from app.main import app
from app.models import AgentRun


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
        # 模型给的调用标识要一路传下去：结果靠它对回自己的调用，而不是靠名字
        assert events[1]["call_id"] == "call_1"
        assert approval["call_id"] == "call_1"

        listed = client.get(f"/api/agent/runs/{approval['run_id']}/approvals")
        assert listed.json()["data"]["items"][0]["status"] == "pending"
        history_path = f"/api/conversations/{conversation_id}"
        waiting = client.get(history_path, params={"message_limit": 1}).json()["data"]
        assert waiting["runs"][0]["id"] == approval["run_id"]
        assert waiting["runs"][0]["user_message_id"] == events[0]["user_message_id"]
        assert waiting["runs"][0]["assistant_message_id"] is None

        decided = client.post(
            f"/api/agent/runs/{approval['run_id']}/approvals/{approval['approval_id']}",
            json={"decision": "approve"},
        )
        resumed = _read_events(decided)
        assert [event["type"] for event in resumed] == ["tool_result", "run_finished"]
        assert resumed[0]["ok"] is True
        assert resumed[0]["call_id"] == "call_1"

        steps = client.get(f"/api/agent/runs/{approval['run_id']}/steps").json()["data"]["items"]
        calls = [step for step in steps if step["kind"] == "tool_call"]
        results = [step for step in steps if step["kind"] == "tool_result"]
        assert [step["call_id"] for step in calls] == ["call_1"]
        assert [step["call_id"] for step in results] == ["call_1"]
        completed = client.get(history_path, params={"message_limit": 1}).json()["data"]
        assert completed["runs"][0]["id"] == approval["run_id"]
        assert completed["runs"][0]["assistant_message_id"] == resumed[-1]["assistant_message_id"]

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


def test_replay_is_linked_by_message_ids_across_runs_and_pages(client: TestClient):
    conversation_id = _conversation(client)
    fake = FakeLLM(
        tool_script=[
            tool_reply("calculator", {"expression": "2+3"}),
            final_reply("计算完成"),
            tool_reply("calculator", {"expression": "6*7"}),
            final_reply("计算完成"),
        ]
    )
    app.dependency_overrides[get_user_llm] = lambda: fake
    path = f"/api/conversations/{conversation_id}"
    runs = []
    try:
        for _ in range(2):
            with client.stream(
                "POST", f"{path}/agent/stream", json={"content": "计算一下"}
            ) as stream:
                events = _read_events(stream)
                runs.append((events[0], events[-1]))
    finally:
        app.dependency_overrides.pop(get_user_llm, None)

    latest = client.get(path, params={"message_limit": 2}).json()["data"]
    older = client.get(
        path, params={"message_limit": 2, "before_message_id": latest["next_before_message_id"]}
    ).json()["data"]
    assert older["next_before_message_id"] is None
    for (started, finished), page, expression, value in zip(
        runs, (older, latest), ("2+3", "6*7"), ("5", "42"), strict=True
    ):
        user_id, assistant_id = [message["id"] for message in page["messages"]]
        assert started["user_message_id"] == user_id
        assert finished["assistant_message_id"] == assistant_id
        assert [(run["id"], run["status"], run["visible_step_count"]) for run in page["runs"]] == [
            (started["run_id"], "completed", 2)
        ]
        # 摘要还要带 request_id / finished_time，断线核对才能对齐到这次运行
        assert page["runs"][0]["request_id"] is None
        assert page["runs"][0]["finished_time"] is not None
        response = client.get(f"/api/agent/runs/{started['run_id']}/steps")
        assert response.status_code == 200
        steps = response.json()["data"]["items"]
        assert [step["kind"] for step in steps] == ["tool_call", "tool_result"]
        assert steps[0]["tool_args"] == {"expression": expression}
        assert steps[1]["content"] == value

    # 旧接口仍可一次读取全部消息。
    assert len(client.get(path).json()["data"]["messages"]) == 4
    other_path = f"/api/conversations/{_conversation(client)}"
    assert client.get(other_path, params={"message_limit": 2}).json()["data"]["runs"] == []


@pytest.mark.usefixtures("llm")
def test_replay_does_not_attach_unlinked_legacy_run_to_a_message(
    client: TestClient, db_session: Session
):
    conversation_id = _conversation(client)
    path = f"/api/conversations/{conversation_id}"
    with client.stream("POST", f"{path}/agent/stream", json={"content": "算一下"}) as stream:
        run_id = _read_events(stream)[0]["run_id"]
    run = db_session.get(AgentRun, run_id)
    run.user_message_id = None
    run.assistant_message_id = None
    db_session.commit()
    page = client.get(path, params={"message_limit": 10}).json()["data"]
    assert page["runs"] == []
    assert len(page["messages"]) == 2
    assert "legacy_runs" not in page


@pytest.mark.usefixtures("llm")
def test_foreign_account_cannot_fetch_replay(client: TestClient, anon_client: TestClient):
    conversation_id = _conversation(client)
    path = f"/api/conversations/{conversation_id}"
    with client.stream("POST", f"{path}/agent/stream", json={"content": "算一下"}) as stream:
        run_id = _read_events(stream)[0]["run_id"]
    assert anon_client.get(f"/api/agent/runs/{run_id}/steps").status_code == 401
    anon_client.post(
        "/api/auth/register",
        json={"email": "replay-other@example.com", "password": "password123"},
    )
    assert anon_client.get(f"/api/agent/runs/{run_id}/steps").status_code == 404
    assert anon_client.get(path, params={"message_limit": 2}).status_code == 404


@pytest.mark.usefixtures("llm")
def test_run_detail_answers_where_and_what(client: TestClient):
    """断线后只发一个请求就要同时拿到「跑到哪了」和「跑了什么」。"""
    conversation_id = _conversation(client)
    with client.stream(
        "POST", f"/api/conversations/{conversation_id}/agent/stream", json={"content": "算一下"}
    ) as stream:
        run_id = _read_events(stream)[0]["run_id"]

    detail = client.get(f"/api/agent/runs/{run_id}").json()["data"]
    assert detail["id"] == run_id
    assert detail["conversation_id"] == conversation_id
    assert detail["status"] == "completed"
    assert detail["finished_time"] is not None
    assert detail["error_message"] is None
    assert [step["kind"] for step in detail["steps"]] == [
        "user_message",
        "tool_call",
        "tool_result",
        "final_answer",
    ]


@pytest.mark.usefixtures("llm")
def test_run_detail_reports_request_id_and_failure_reason(client: TestClient, db_session: Session):
    """request_id 与失败原因都要能从接口读回来：前端据此判定「能否安全重发」。"""
    conversation_id = _conversation(client)
    request_id = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "算一下", "execution": "auto", "request_id": request_id},
    ) as stream:
        run_id = _read_events(stream)[0]["run_id"]

    # 历史页摘要带 request_id，前端才能把核对对齐到具体一次运行
    page = client.get(f"/api/conversations/{conversation_id}", params={"message_limit": 10})
    summary = page.json()["data"]["runs"][0]
    assert summary["request_id"] == request_id
    assert summary["error_message"] is None
    assert summary["finished_time"] is not None

    # 服务端记下的失败原因要原样透出，前端不再自己编通用文案
    run = db_session.get(AgentRun, run_id)
    run.status = "failed"
    run.error_message = "运行被中断"
    db_session.commit()
    detail = client.get(f"/api/agent/runs/{run_id}").json()["data"]
    assert detail["status"] == "failed"
    assert detail["error_message"] == "运行被中断"


@pytest.mark.usefixtures("llm")
def test_run_detail_is_scoped_to_the_owner(client: TestClient, anon_client: TestClient):
    conversation_id = _conversation(client)
    with client.stream(
        "POST", f"/api/conversations/{conversation_id}/agent/stream", json={"content": "算一下"}
    ) as stream:
        run_id = _read_events(stream)[0]["run_id"]

    assert anon_client.get(f"/api/agent/runs/{run_id}").status_code == 401
    anon_client.post(
        "/api/auth/register",
        json={"email": "run-detail-other@example.com", "password": "password123"},
    )
    assert anon_client.get(f"/api/agent/runs/{run_id}").status_code == 404


@pytest.mark.usefixtures("llm")
def test_runs_can_be_located_by_request_id(client: TestClient):
    """断线后只凭客户端手里的 request_id 就能问出「这条提交落库了吗」。"""
    conversation_id = _conversation(client)
    request_id = "9b2f0c4e-1d3a-4c8b-8f7e-2a5d6c7b8a91"
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "算一下", "execution": "auto", "request_id": request_id},
    ) as stream:
        run_id = _read_events(stream)[0]["run_id"]

    found = client.get(
        f"/api/conversations/{conversation_id}/agent/runs", params={"request_id": request_id}
    ).json()["data"]
    assert [item["id"] for item in found["items"]] == [run_id]
    assert found["items"][0]["request_id"] == request_id

    # 同一个 request_id 重复提交是 409（已有去重），这里确认它指向的仍是同一条运行
    duplicate = client.post(
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "算一下", "execution": "auto", "request_id": request_id},
    )
    assert duplicate.status_code == 409

    # 没落库的 request_id 返回 404：前端据此判定可以安全重发
    missing = client.get(
        f"/api/conversations/{conversation_id}/agent/runs",
        params={"request_id": "00000000-0000-4000-8000-000000000000"},
    )
    assert missing.status_code == 404
    assert missing.json()["message"] == "这次提交还没有落库，可以重新发送"


@pytest.mark.usefixtures("llm")
def test_steps_endpoint_answers_incremental_reads(client: TestClient):
    """轮询只要增量，同时还能拿到运行状态，一个请求回答两个问题。"""
    conversation_id = _conversation(client)
    with client.stream(
        "POST", f"/api/conversations/{conversation_id}/agent/stream", json={"content": "算一下"}
    ) as stream:
        run_id = _read_events(stream)[0]["run_id"]

    full = client.get(f"/api/agent/runs/{run_id}/steps").json()["data"]
    assert [step["kind"] for step in full["items"]] == ["tool_call", "tool_result"]
    assert full["status"] == "completed"
    assert full["visible_step_count"] == 2
    assert full["finished_time"] is not None
    assert full["error_message"] is None

    incremental = client.get(f"/api/agent/runs/{run_id}/steps", params={"since_seq": 2}).json()[
        "data"
    ]
    assert [step["kind"] for step in incremental["items"]] == ["tool_result"]
    # 总数不受 since_seq 影响，前端据此判断「还有没有更早的没拿到」
    assert incremental["visible_step_count"] == 2

    nothing_new = client.get(f"/api/agent/runs/{run_id}/steps", params={"since_seq": 99}).json()[
        "data"
    ]
    assert nothing_new["items"] == []
    assert nothing_new["status"] == "completed"


@pytest.mark.usefixtures("llm")
def test_stop_refuses_finished_run(client: TestClient):
    conversation_id = _conversation(client)
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/agent/stream",
        json={"content": "2 的 10 次方"},
    ) as response:
        events = _read_events(response)
    run_id = events[0]["run_id"]

    stopped = client.post(f"/api/agent/runs/{run_id}/stop")
    assert stopped.status_code == 409
    assert stopped.json()["message"] == "这次运行已经结束"


def test_stop_keeps_generated_text_as_message(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    # 真实断线里这一列由后台线程写；这里直接造出「跑到一半」的样子
    # 运行归本进程负责但线程刚好收尾：终止走「没有线程可停」的兜底路径
    monkeypatch.setattr(run_hub, "owns", lambda _run_id: True)
    conversation_id = _conversation(client)
    run = AgentRun(
        conversation_id=conversation_id,
        user_id=_user_id(client),
        status="running",
        draft_content="我先把两个数加起来",
    )
    db_session.add(run)
    db_session.commit()

    stopped = client.post(f"/api/agent/runs/{run.id}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["data"]["status"] == "cancelled"

    db_session.refresh(run)
    assert run.status == "cancelled"
    assert run.stop_reason == "user_cancelled"
    assert run.draft_content is None
    assert run.finished_time is not None
    history = client.get(f"/api/conversations/{conversation_id}?message_limit=50").json()["data"]
    assert [item["content"] for item in history["messages"] if item["role"] == "assistant"] == [
        "我先把两个数加起来"
    ]


def test_stop_refuses_run_owned_by_another_process(client: TestClient, db_session: Session):
    """多 worker 部署时，另一个进程里的运行不能由这个进程标成取消。"""
    conversation_id = _conversation(client)
    run = AgentRun(conversation_id=conversation_id, user_id=_user_id(client), status="running")
    db_session.add(run)
    db_session.commit()

    refused = client.post(f"/api/agent/runs/{run.id}/stop")
    assert refused.status_code == 409
    assert "另一个进程" in refused.json()["message"]

    db_session.refresh(run)
    assert run.status == "running"


def test_stop_cancels_run_waiting_for_approval_without_a_thread(
    client: TestClient, db_session: Session
):
    """等审批时没有执行线程，终止直接落终态——这不是多进程问题。"""
    conversation_id = _conversation(client)
    run = AgentRun(
        conversation_id=conversation_id, user_id=_user_id(client), status="waiting_approval"
    )
    db_session.add(run)
    db_session.commit()

    stopped = client.post(f"/api/agent/runs/{run.id}/stop")
    assert stopped.status_code == 200
    db_session.refresh(run)
    assert run.status == "cancelled"


def test_stream_refuses_run_owned_by_another_process(client: TestClient, db_session: Session):
    conversation_id = _conversation(client)
    run = AgentRun(conversation_id=conversation_id, user_id=_user_id(client), status="running")
    db_session.add(run)
    db_session.commit()

    refused = client.get(f"/api/agent/runs/{run.id}/stream")
    assert refused.status_code == 409
    assert "另一个进程" in refused.json()["message"]


def test_subscribe_starts_with_snapshot(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    # 运行归本进程负责、但线程已经收尾：先给快照，后面没有实时事件
    monkeypatch.setattr(run_hub, "owns", lambda _run_id: True)
    conversation_id = _conversation(client)
    run = AgentRun(
        conversation_id=conversation_id,
        user_id=_user_id(client),
        status="running",
        draft_content="先说一半",
    )
    db_session.add(run)
    db_session.commit()

    with client.stream("GET", f"/api/agent/runs/{run.id}/stream") as response:
        assert response.status_code == 200
        events = _read_events(response)
    assert [event["type"] for event in events] == ["run_snapshot"]
    assert events[0]["draft_content"] == "先说一半"
    assert events[0]["status"] == "running"
    assert events[0]["run_id"] == run.id


def _user_id(client: TestClient) -> int:
    return client.get("/api/auth/me").json()["data"]["id"]


@pytest.mark.usefixtures("llm")
def test_regenerate_replaces_the_old_answer(client: TestClient):
    conversation_id = _conversation(client)
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/agent/stream",
        json={"content": "上次你说什么"},
    ) as response:
        first = _read_events(response)
    run_id = first[0]["run_id"]
    before = client.get(f"/api/conversations/{conversation_id}?message_limit=50").json()["data"]
    assert [item["role"] for item in before["messages"]] == ["user", "assistant"]

    with client.stream("POST", f"/api/agent/runs/{run_id}/regenerate") as response:
        assert response.status_code == 200
        again = _read_events(response)
    assert again[0]["type"] == "run_started"
    assert again[-1]["type"] == "run_finished"

    after = client.get(f"/api/conversations/{conversation_id}?message_limit=50").json()["data"]
    # 旧的问答一起删掉了，历史里只有一问一答，不会出现两个相同的问题
    assert [item["role"] for item in after["messages"]] == ["user", "assistant"]
    assert after["messages"][0]["content"] == "上次你说什么"


@pytest.mark.usefixtures("llm")
def test_regenerate_refuses_running_run(client: TestClient, db_session: Session):
    conversation_id = _conversation(client)
    run = AgentRun(conversation_id=conversation_id, user_id=_user_id(client), status="running")
    db_session.add(run)
    db_session.commit()

    response = client.post(f"/api/agent/runs/{run.id}/regenerate")
    assert response.status_code == 409
    assert response.json()["message"] == "这次运行还没结束，先终止再重新生成"
