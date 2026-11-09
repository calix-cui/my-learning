"""设置接口与账号资料接口的接口层测试。

覆盖：未登录 401、默认回落到环境变量、保存后读回、无主密钥时拒绝存 Key、
导出 JSON / Markdown、改名、注销（密码错误 / 正确）以及注销后的登录态失效。
"""

import json

import pytest
from cryptography.fernet import Fernet

from app.config import Settings, settings


@pytest.fixture()
def secret_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        settings, "app_secret_key", Settings.model_fields["app_secret_key"].annotation(key)
    )
    return key


def test_settings_require_login(anon_client):
    assert anon_client.get("/api/settings/model").status_code == 401
    assert (
        anon_client.post("/api/settings/model/test", json={"provider": "fake"}).status_code == 401
    )
    assert anon_client.get("/api/settings/export").status_code == 401


def test_read_model_settings_inherits_env(client):
    data = client.get("/api/settings/model").json()["data"]

    assert data["inherited_from_env"] is True
    assert data["timeout_seconds"] >= 5
    # 测试环境里 LLM_API_KEY 被清空，因此没有 Key
    assert data["has_api_key"] is False


def test_save_and_read_model_settings(client):
    saved = client.put(
        "/api/settings/model", json={"provider": "fake", "timeout_seconds": 45}
    ).json()["data"]
    assert saved["provider"] == "fake"
    assert saved["timeout_seconds"] == 45
    assert saved["inherited_from_env"] is False

    read_back = client.get("/api/settings/model").json()["data"]
    assert read_back["timeout_seconds"] == 45


def test_save_api_key_without_secret_key_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        settings, "app_secret_key", Settings.model_fields["app_secret_key"].annotation("")
    )

    response = client.put("/api/settings/model", json={"api_key": "sk-test-0001"})

    assert response.status_code == 400
    assert "APP_SECRET_KEY" in response.json()["message"]


@pytest.mark.usefixtures("secret_key")
def test_save_api_key_with_secret_key_hides_plaintext(client):
    response = client.put(
        "/api/settings/model",
        json={
            "provider": "openai",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-secret-4321",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["has_api_key"] is True
    assert data["api_key_hint"] == "4321"
    assert "sk-secret-4321" not in response.text


def test_test_model_endpoint_with_fake(client):
    data = client.post("/api/settings/model/test", json={"provider": "fake"}).json()["data"]

    assert data["ok"] is True
    assert data["latency_ms"] >= 0


def test_test_model_endpoint_reports_missing_key(client, monkeypatch):
    monkeypatch.setattr(
        settings, "app_secret_key", Settings.model_fields["app_secret_key"].annotation("")
    )
    data = client.post(
        "/api/settings/model/test",
        json={
            "provider": "openai",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
    ).json()["data"]

    assert data["ok"] is False
    assert "API Key" in data["message"]


def test_export_json_contains_conversations(client):
    created = client.post("/api/conversations", json={"title": "导出用会话"}).json()["data"]
    client.post(f"/api/conversations/{created['id']}/messages", json={"content": "导出这段"})

    response = client.get("/api/settings/export?format=json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = json.loads(response.text)
    assert payload["schema"] == "my-agent.export.v1"
    assert payload["user"]["email"] == "user@example.com"
    titles = [item["title"] for item in payload["conversations"]]
    assert "导出用会话" in titles
    assert any(
        msg["content"] == "导出这段"
        for item in payload["conversations"]
        for msg in item["messages"]
    )


def test_export_markdown_contains_headers(client):
    client.post("/api/conversations", json={"title": "Markdown 会话"})

    response = client.get("/api/settings/export?format=markdown")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text.startswith("# My Agent 对话导出")
    assert "Markdown 会话" in response.text


def test_export_rejects_unknown_format(client):
    assert client.get("/api/settings/export?format=csv").status_code == 422


def test_update_display_name(client):
    data = client.patch("/api/auth/me", json={"display_name": "  小张  "}).json()["data"]

    assert data["display_name"] == "小张"
    assert client.get("/api/auth/me").json()["data"]["display_name"] == "小张"


def test_clear_display_name(client):
    client.patch("/api/auth/me", json={"display_name": "小张"})
    data = client.patch("/api/auth/me", json={"display_name": ""}).json()["data"]

    assert data["display_name"] is None


def test_delete_account_requires_correct_password(client):
    wrong = client.request("DELETE", "/api/auth/me", json={"password": "wrong-password"})
    assert wrong.status_code == 400
    assert wrong.json()["message"] == "密码不正确"

    ok = client.request("DELETE", "/api/auth/me", json={"password": "password123"})
    assert ok.status_code == 200
    assert ok.json()["message"] == "账号已注销"

    # 注销后同一个客户端再访问应 401
    assert client.get("/api/auth/me").status_code == 401


def test_delete_account_removes_owned_data(client, db_session):
    """注销要连带删掉会话（NOT NULL 的 conversations.user_id 不能被置空）。"""
    from sqlalchemy import func, select

    from app.models import Conversation, Message

    created = client.post("/api/conversations", json={"title": "注销前的会话"}).json()["data"]
    client.post(f"/api/conversations/{created['id']}/messages", json={"content": "留个记录"})

    ok = client.request("DELETE", "/api/auth/me", json={"password": "password123"})
    assert ok.status_code == 200

    assert db_session.scalar(select(func.count()).select_from(Conversation)) == 0
    assert db_session.scalar(select(func.count()).select_from(Message)) == 0
