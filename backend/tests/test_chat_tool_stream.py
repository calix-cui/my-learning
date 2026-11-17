"""普通聊天的流式工具执行、审批和最终消息。"""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.llm import get_user_llm
from app.llm.openai_compatible import OpenAICompatibleClient
from app.main import app
from app.mcp.manager import reset_manager
from app.models import AgentRun, McpServer, UserSettings

SEARCH_SERVER = Path(__file__).parent / "fixtures" / "mcp_search_server.py"
SEARCH_TOOL = "mcp__web__web_search"


def _model_stream(*frames, finish="stop") -> httpx.Response:
    choices = [{"delta": frame, "finish_reason": None} for frame in frames]
    if finish:
        choices.append({"delta": {}, "finish_reason": finish})
    data = [f"data: {json.dumps({'choices': [item]}, ensure_ascii=False)}" for item in choices]
    return httpx.Response(200, text="\n\n".join([*data, "data: [DONE]", ""]))


def _stream_events(response: httpx.Response) -> list[dict]:
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]


def _fragment(index, *, call_id=None, name=None, arguments=None):
    function = {
        key: value
        for key, value in {"name": name, "arguments": arguments}.items()
        if value is not None
    }
    result = {"index": index, "function": function}
    if call_id is not None:
        result["id"] = call_id
    return {"tool_calls": [result]}


def _start(client: TestClient, content: str, **fields):
    created = client.post("/api/conversations", json={}).json()["data"]["id"]
    path = f"/api/conversations/{created}"
    return path, _stream_events(
        client.post(
            f"{path}/messages/stream", json={"content": content, "execution": "auto", **fields}
        )
    )


@pytest.fixture
def provider():
    payloads = []
    replies = []

    def respond(request):
        payloads.append(json.loads(request.content))
        assert replies, "运行发起了意外的额外模型请求"
        return replies.pop(0)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    llm = OpenAICompatibleClient(
        "https://api.deepseek.com/v1", "test", "deepseek-chat", client=client
    )
    app.dependency_overrides[get_user_llm] = lambda: llm
    try:
        yield payloads, replies, llm
    finally:
        app.dependency_overrides.pop(get_user_llm, None)
        client.close()


def test_ordinary_chat_streams_after_using_clock_and_deduplicates_submission(client, provider):
    payloads, replies, _ = provider
    replies.extend(
        [
            _model_stream(
                {"content": "我先查询。"},
                _fragment(0, call_id="call_clock", name="no", arguments='{"time'),
                _fragment(0, name="w", arguments='zone":"UTC"}'),
                finish="tool_calls",
            ),
            _model_stream({"content": "当前"}, {"content": "是 UTC 时间。"}),
        ]
    )
    request_id = "e897e2ea-053b-47d6-8dd7-51320957d7dc"
    path, events = _start(client, "现在 UTC 时间是什么？", request_id=request_id)
    assert [event["type"] for event in events] == [
        "run_started",
        "assistant_delta",
        "assistant_preview_reset",
        "assistant_text",
        "tool_call",
        "tool_result",
        "assistant_delta",
        "assistant_delta",
        "run_finished",
    ]
    assert events[4]["args"] == {"timezone": "UTC"}
    assert events[5]["ok"] and "UTC" in events[5]["content"]
    assert payloads[0]["tool_choice"] == "auto"
    assert payloads[0]["thinking"] == {"type": "disabled"}
    assert payloads[1]["messages"][-1]["tool_call_id"] == "call_clock"
    assert payloads[1]["messages"][-1]["content"] == events[5]["content"]
    assert events[-1]["content"] == "当前是 UTC 时间。"
    history = client.get(path, params={"message_limit": 50}).json()["data"]
    assert history["runs"][0]["assistant_message_id"] == events[-1]["assistant_message_id"]
    duplicate = client.post(
        f"{path}/messages/stream",
        json={"content": "现在 UTC 时间是什么？", "execution": "auto", "request_id": request_id},
    )
    assert duplicate.status_code == 409
    assert len(payloads) == 2


@pytest.mark.parametrize("tool_capable", [True, False])
def test_plain_answer_uses_one_request_and_streams_without_a_tool(client, provider, tool_capable):
    payloads, replies, llm = provider
    llm.supports_tool_calls = tool_capable
    replies.append(_model_stream({"content": "你好"}, {"content": "！"}))
    _, events = _start(client, "你好")
    assert [event["type"] for event in events] == [
        "run_started",
        "assistant_delta",
        "assistant_delta",
        "run_finished",
    ]
    assert ("tools" in payloads[0]) == tool_capable
    assert len(payloads) == 1
    assert "缺少所需工具" in payloads[0]["messages"][0]["content"]


def test_partial_tool_stream_never_executes(client, provider):
    _, replies, _ = provider
    replies.append(
        _model_stream(_fragment(0, call_id="clock", name="now", arguments="{}"), finish=None)
    )
    _, events = _start(client, "现在几点")
    assert [event["type"] for event in events] == ["run_started", "error"]


def test_model_timeout_reports_failure_before_tool_execution(client, provider):
    _, replies, _ = provider

    class TimeoutStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"half"}}]}\n\n'
            raise httpx.ReadTimeout("timed out")

    replies.append(httpx.Response(200, stream=TimeoutStream()))
    _, events = _start(client, "查时间")
    assert [event["type"] for event in events] == ["run_started", "assistant_delta", "error"]
    assert events[-1]["code"] == 504


def test_multiple_calls_keep_original_order_and_disabled_tool_cannot_run(
    client, provider, db_session: Session
):
    payloads, replies, _ = provider
    account_id = client.get("/api/auth/me").json()["data"]["id"]
    db_session.add(UserSettings(user_id=account_id, tools_disabled=["now"]))
    db_session.commit()
    replies.extend(
        [
            _model_stream(
                _fragment(1, call_id="clock", name="now", arguments="{}"),
                _fragment(0, call_id="calc", name="calculator", arguments='{"expression":"7*6"}'),
                finish="tool_calls",
            ),
            _model_stream({"content": "计算完成。"}),
        ]
    )
    _, events = _start(client, "算一下并报时")
    calls = [event for event in events if event["type"] == "tool_call"]
    assert [call["tool"] for call in calls] == ["calculator", "now"]
    results = [event for event in events if event["type"] == "tool_result"]
    assert results[0]["ok"] and results[0]["content"] == "42"
    assert not results[1]["ok"] and "未启用" in results[1]["content"]
    assert "now" not in [tool["function"]["name"] for tool in payloads[0]["tools"]]


@pytest.mark.parametrize("effort", ["none", "high"])
def test_web_search_requires_approval_and_replays_real_mcp_result(
    client, db_session: Session, provider, effort
):
    payloads, replies, _ = provider
    account_id = client.get("/api/auth/me").json()["data"]["id"]
    db_session.add(
        McpServer(
            user_id=account_id,
            slug="web",
            display_name="网页搜索",
            enabled=True,
            transport="stdio",
            command="uv",
            args=["run", "--no-sync", "python", str(SEARCH_SERVER)],
        )
    )
    db_session.commit()
    first = _fragment(
        0, call_id="search_1", name=SEARCH_TOOL, arguments='{"query":"Agent 怎么实现"}'
    )
    if effort == "high":
        first["reasoning_content"] = "私有模型上下文"
    replies.extend(
        [
            _model_stream(first, finish="tool_calls"),
            _model_stream({"content": "可以使用工具调用循环。"}),
        ]
    )
    reset_manager()
    try:
        path, initial = _start(client, "请帮我搜索 Agent 怎么实现", reasoning_effort=effort)
        assert [event["type"] for event in initial] == [
            "run_started",
            "tool_call",
            "approval_required",
        ]
        approval = initial[-1]
        assert approval["tool"] == SEARCH_TOOL
        assert "私有模型上下文" not in json.dumps(initial, ensure_ascii=False)
        approval_path = f"/api/agent/runs/{approval['run_id']}/approvals/{approval['approval_id']}"
        approved = client.post(approval_path, json={"decision": "approve"})
        events = _stream_events(approved)
        assert events[0]["ok"] and "Function calling" in events[0]["content"]
        assert events[-1]["type"] == "run_finished"
        answer = events[-1]["content"]
        assert "https://developers.openai.com/" in answer
        assert "javascript" not in answer
        assert client.get(path).json()["data"]["messages"][-1]["content"] == answer
        assert payloads[1]["messages"][-1]["tool_call_id"] == "search_1"
        assert payloads[1]["thinking"]["type"] == ("enabled" if effort == "high" else "disabled")
        if effort == "high":
            assert payloads[1]["messages"][-2]["reasoning_content"] == "私有模型上下文"
        assert db_session.get(AgentRun, approval["run_id"]).approval_context is None
        assert client.post(approval_path, json={"decision": "approve"}).status_code == 409
        assert len(payloads) == 2
    finally:
        reset_manager()
