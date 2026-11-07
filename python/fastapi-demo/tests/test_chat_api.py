"""会话接口层测试：用内存 SQLite 覆盖 get_db，走完整的 HTTP 链路。"""

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.main import app
from app.models import Message


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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
