"""会话接口层测试：用内存 SQLite 覆盖 get_db，走完整的 HTTP 链路。"""

from app.llm import LLMError, LLMTimeoutError, get_user_llm
from app.main import app
from app.models import Message


def test_create_conversation_returns_default_title(client):
    response = client.post("/api/conversations", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["data"]["title"] == "新会话"
    assert body["data"]["agent_key"] == "default"
    assert body["data"]["id"] > 0
    # 时间统一序列化成秒级字符串
    assert len(body["data"]["create_time"]) == 19


def test_list_conversations_includes_message_count(client, db_session):
    created = client.post("/api/conversations", json={"title": "带消息"}).json()["data"]
    db_session.add(Message(conversation_id=created["id"], role="user", content="你好"))
    db_session.commit()
    client.post("/api/conversations", json={"title": "空会话"})

    response = client.get("/api/conversations")

    assert response.status_code == 200
    page = response.json()["data"]
    assert page["total"] == 2
    counts = {item["title"]: item["message_count"] for item in page["items"]}
    assert counts == {"带消息": 1, "空会话": 0}


def test_list_conversations_validates_page_size(client):
    response = client.get("/api/conversations", params={"page_size": 101})

    assert response.status_code == 422


def test_get_conversation_returns_messages(client, db_session):
    created = client.post("/api/conversations", json={"title": "详情"}).json()["data"]
    db_session.add(Message(conversation_id=created["id"], role="user", content="第一句"))
    db_session.add(
        Message(conversation_id=created["id"], role="assistant", content="第二句", model="fake")
    )
    db_session.commit()

    response = client.get(f"/api/conversations/{created['id']}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "详情"
    assert [m["content"] for m in data["messages"]] == ["第一句", "第二句"]
    assert data["messages"][1]["model"] == "fake"


def test_get_missing_conversation_returns_404(client):
    response = client.get("/api/conversations/9999")

    assert response.status_code == 404
    assert response.json() == {"code": 404, "message": "会话不存在", "data": None}


def test_rename_conversation(client):
    created = client.post("/api/conversations", json={"title": "旧名"}).json()["data"]

    response = client.patch(f"/api/conversations/{created['id']}", json={"title": " 新名 "})

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "新名"


def test_rename_conversation_blank_returns_400(client):
    created = client.post("/api/conversations", json={"title": "旧名"}).json()["data"]

    response = client.patch(f"/api/conversations/{created['id']}", json={"title": "   "})

    assert response.status_code == 400
    assert response.json()["message"] == "会话标题不能只包含空白"


def test_rename_conversation_empty_returns_422(client):
    created = client.post("/api/conversations", json={"title": "旧名"}).json()["data"]

    response = client.patch(f"/api/conversations/{created['id']}", json={"title": ""})

    assert response.status_code == 422


def test_delete_conversation_then_404(client):
    created = client.post("/api/conversations", json={"title": "待删"}).json()["data"]

    deleted = client.delete(f"/api/conversations/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"code": 200, "message": "请求成功", "data": None}

    assert client.get(f"/api/conversations/{created['id']}").status_code == 404


def test_send_message_returns_both_messages(client):
    created = client.post("/api/conversations", json={}).json()["data"]

    response = client.post(
        f"/api/conversations/{created['id']}/messages", json={"content": "  你好  "}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_message"]["content"] == "你好"
    assert data["user_message"]["role"] == "user"
    assert data["user_message"]["model"] is None
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["content"] == "[fake] 收到：你好"
    assert data["assistant_message"]["model"] == "fake"


def test_send_message_auto_titles_conversation(client):
    created = client.post("/api/conversations", json={}).json()["data"]

    client.post(f"/api/conversations/{created['id']}/messages", json={"content": "帮我写周报"})

    detail = client.get(f"/api/conversations/{created['id']}").json()["data"]
    assert detail["title"] == "帮我写周报"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


def test_send_message_to_missing_conversation_returns_404(client):
    response = client.post("/api/conversations/9999/messages", json={"content": "你好"})

    assert response.status_code == 404
    assert response.json()["message"] == "会话不存在"


def test_send_message_blank_returns_400(client):
    created = client.post("/api/conversations", json={}).json()["data"]

    response = client.post(f"/api/conversations/{created['id']}/messages", json={"content": "   "})

    assert response.status_code == 400
    assert response.json()["message"] == "消息内容不能只包含空白"


def test_send_message_empty_returns_422(client):
    created = client.post("/api/conversations", json={}).json()["data"]

    response = client.post(f"/api/conversations/{created['id']}/messages", json={"content": ""})

    assert response.status_code == 422


def test_send_message_model_failure_returns_502(client, db_session):
    created = client.post("/api/conversations", json={}).json()["data"]
    app.dependency_overrides[get_user_llm] = lambda: _FailingLLM(LLMError())

    try:
        response = client.post(
            f"/api/conversations/{created['id']}/messages", json={"content": "你好"}
        )
    finally:
        app.dependency_overrides.pop(get_user_llm, None)

    assert response.status_code == 502
    assert response.json() == {"code": 502, "message": "模型服务不可用", "data": None}
    assert db_session.query(Message).count() == 0


def test_send_message_model_timeout_returns_504(client, db_session):
    assert db_session.query(Message).count() == 0  # 前置：库里本来没有消息
    created = client.post("/api/conversations", json={}).json()["data"]
    app.dependency_overrides[get_user_llm] = lambda: _FailingLLM(LLMTimeoutError())

    try:
        response = client.post(
            f"/api/conversations/{created['id']}/messages", json={"content": "你好"}
        )
    finally:
        app.dependency_overrides.pop(get_user_llm, None)

    assert response.status_code == 504
    assert response.json()["message"] == "模型服务超时"


def _read_events(response) -> list[dict]:
    """把 SSE 响应体解成事件列表。"""
    import json

    events = []
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


class _FailingLLM:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.model = "failing"

    def stream(self, _messages):
        raise self.error

    def chat(self, _messages):
        raise self.error


def test_stream_message_sends_sse_events(client, db_session):
    created = client.post("/api/conversations", json={}).json()["data"]

    with client.stream(
        "POST", f"/api/conversations/{created['id']}/messages/stream", json={"content": "你好"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _read_events(response)

    types = [e["type"] for e in events]
    assert types[0] == "meta"
    assert types[-1] == "done"
    assert set(types[1:-1]) == {"delta"}
    assert "".join(e["content"] for e in events if e["type"] == "delta").startswith("[fake] 收到：")
    assert events[-1]["conversation_title"] == "你好"
    assert db_session.query(Message).count() == 2


def test_stream_message_blank_content_returns_json_400(client):
    created = client.post("/api/conversations", json={}).json()["data"]

    response = client.post(
        f"/api/conversations/{created['id']}/messages/stream", json={"content": "   "}
    )

    assert response.status_code == 400
    assert response.json()["message"] == "消息内容不能只包含空白"


def test_stream_message_missing_conversation_returns_404(client):
    response = client.post("/api/conversations/9999/messages/stream", json={"content": "你好"})

    assert response.status_code == 404
    assert response.json()["message"] == "会话不存在"


def test_stream_message_llm_error_becomes_error_event(client, db_session):
    created = client.post("/api/conversations", json={}).json()["data"]
    app.dependency_overrides[get_user_llm] = lambda: _FailingLLM(LLMError())

    try:
        with client.stream(
            "POST",
            f"/api/conversations/{created['id']}/messages/stream",
            json={"content": "你好"},
        ) as response:
            assert response.status_code == 200
            events = _read_events(response)
    finally:
        app.dependency_overrides.pop(get_user_llm, None)

    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == 502
    assert db_session.query(Message).count() == 0
