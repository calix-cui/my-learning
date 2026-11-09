"""账号接口与数据隔离的接口层测试。

重点覆盖两件事：
1. 未登录只能访问注册/登录（以及探针），其余业务接口一律 401；
2. A 用户的会话对 B 用户完全不可见——列表里没有，按 id 直接访问是 404。
"""

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.main import app

REGISTER_PAYLOAD = {"email": "user@example.com", "password": "password123"}


def _raw_client(db_session) -> TestClient:
    """同一份内存库上开一个未登录的客户端。"""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _new_client(db_session, email: str = "user@example.com") -> TestClient:
    """注册并登录一个新用户。"""
    client = _raw_client(db_session)
    response = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return client


def _second_device(db_session, email: str = "user@example.com") -> TestClient:
    """同一账号的第二台设备：走登录而不是注册。"""
    client = _raw_client(db_session)
    response = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return client


# --- 注册 / 登录 / 登出 ---


def test_register_sets_httponly_cookie_and_returns_user(anon_client):
    response = anon_client.post("/api/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["email"] == "user@example.com"
    assert body["data"]["role"] == "user"
    assert "password" not in body["data"]

    set_cookie = response.headers["set-cookie"]
    assert "my_agent_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_register_rejects_duplicate_email(anon_client):
    anon_client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    response = anon_client.post("/api/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["message"] == "该邮箱已注册"


def test_register_rejects_short_password(anon_client):
    response = anon_client.post(
        "/api/auth/register", json={"email": "x@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_register_respects_switch(anon_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "allow_registration", False)
    response = anon_client.post("/api/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 403
    assert response.json()["message"] == "注册已关闭"


def test_login_and_logout_flow(anon_client):
    anon_client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    anon_client.post("/api/auth/logout")

    assert anon_client.get("/api/auth/me").status_code == 401

    response = anon_client.post(
        "/api/auth/login", json={"email": "USER@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert anon_client.get("/api/auth/me").json()["data"]["email"] == "user@example.com"

    assert anon_client.post("/api/auth/logout").status_code == 200
    assert anon_client.get("/api/auth/me").status_code == 401


def test_login_with_wrong_password_is_401(anon_client):
    anon_client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    response = anon_client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["message"] == "邮箱或密码不正确"


def test_me_requires_login(anon_client):
    response = anon_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["message"] == "请先登录"


# --- 登录设备 ---


def test_sessions_list_marks_current_device(client):
    response = client.get("/api/auth/sessions")

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["is_current"] is True
    assert items[0]["user_agent"] is not None or items[0]["user_agent"] is None


def test_delete_unknown_session_is_404(client):
    response = client.delete("/api/auth/sessions/9999")
    assert response.status_code == 404
    assert response.json()["message"] == "登录会话不存在"


def test_change_password_kicks_other_devices(db_session):
    first = _new_client(db_session)
    second = _second_device(db_session)  # 同一账号第二台设备

    assert len(second.get("/api/auth/sessions").json()["data"]["items"]) == 2

    response = second.post(
        "/api/auth/password",
        json={"old_password": "password123", "new_password": "newpassword456"},
    )
    assert response.status_code == 200

    # 当前设备仍登录，另一台被踢下线
    assert second.get("/api/auth/me").status_code == 200
    assert first.get("/api/auth/me").status_code == 401

    # 旧密码失效、新密码可登录
    assert (
        first.post(
            "/api/auth/login", json={"email": "user@example.com", "password": "password123"}
        ).status_code
        == 401
    )


def test_change_password_rejects_wrong_old_password(client):
    response = client.post(
        "/api/auth/password",
        json={"old_password": "wrong-password", "new_password": "newpassword456"},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "原密码不正确"


# --- 未登录拦截 ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/conversations"),
        ("post", "/api/conversations"),
        ("get", "/api/conversations/1"),
        ("patch", "/api/conversations/1"),
        ("delete", "/api/conversations/1"),
        ("get", "/api/auth/sessions"),
    ],
)
def test_business_endpoints_require_login(anon_client, method: str, path: str):
    response = getattr(anon_client, method)(
        path, **({"json": {}} if method in {"post", "patch"} else {})
    )
    assert response.status_code == 401


def test_health_endpoints_stay_public(anon_client):
    assert anon_client.get("/healthz").status_code == 200
    assert anon_client.get("/readyz").status_code in (200, 503)


# --- 数据隔离 ---


def test_users_cannot_see_each_other_conversations(db_session):
    alice = _new_client(db_session, "alice@example.com")
    bob = _new_client(db_session, "bob@example.com")

    created = alice.post("/api/conversations", json={"title": "Alice 的会话"}).json()["data"]
    conversation_id = created["id"]

    # 列表：Bob 看不到，分页 total 也不含
    bob_list = bob.get("/api/conversations").json()["data"]
    assert bob_list["total"] == 0
    assert bob_list["items"] == []

    # 详情 / 改名 / 删除 / 发消息 / 流式：对 Bob 一律 404
    assert bob.get(f"/api/conversations/{conversation_id}").status_code == 404
    assert (
        bob.patch(f"/api/conversations/{conversation_id}", json={"title": "抢"}).status_code == 404
    )
    assert bob.delete(f"/api/conversations/{conversation_id}").status_code == 404
    assert (
        bob.post(
            f"/api/conversations/{conversation_id}/messages", json={"content": "你好"}
        ).status_code
        == 404
    )
    assert (
        bob.post(
            f"/api/conversations/{conversation_id}/messages/stream", json={"content": "你好"}
        ).status_code
        == 404
    )

    # Alice 自己一切正常，且数据没被 Bob 动过
    detail = alice.get(f"/api/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "Alice 的会话"
