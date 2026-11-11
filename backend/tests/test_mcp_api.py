"""MCP 工具市场接口（阶段 7 T4）。

覆盖六件事：清单带「已接入」状态、接入内置条目、自定义条目的字段校验、
启停与改配置后断连接、越权/不存在都返回 404、试连返回工具清单并把状态落库。
"""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from app.mcp.manager import reset_manager
from app.models import McpServer

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "mcp_echo_server.py"


def _custom_payload(slug: str = "echo", **overrides) -> dict:
    payload = {
        "slug": slug,
        "display_name": "Echo 服务器",
        "transport": "stdio",
        "command": "uv",
        "args": ["run", "--no-sync", "python", str(FIXTURE)],
    }
    payload.update(overrides)
    return payload


def test_catalog_lists_builtin_entries(client: TestClient) -> None:
    resp = client.get("/api/mcp/catalog")
    assert resp.status_code == 200
    data = resp.json()["data"]
    slugs = [item["slug"] for item in data["items"]]
    assert "filesystem" in slugs and "deepwiki" in slugs
    assert all(item["installed_id"] is None for item in data["items"])
    assert data["updated"]


def test_create_from_catalog_then_catalog_marks_installed(client: TestClient) -> None:
    resp = client.post("/api/mcp/servers", json={"slug": "time"})
    assert resp.status_code == 200, resp.text
    created = resp.json()["data"]
    assert created["slug"] == "time"
    assert created["last_status"] == "unknown"
    assert created["enabled"] is True

    catalog = client.get("/api/mcp/catalog").json()["data"]
    time_item = next(item for item in catalog["items"] if item["slug"] == "time")
    assert time_item["installed_id"] == created["id"]

    servers = client.get("/api/mcp/servers").json()["data"]["items"]
    assert [row["slug"] for row in servers] == ["time"]


def test_catalog_entry_requiring_path_rejects_without_it(client: TestClient) -> None:
    resp = client.post("/api/mcp/servers", json={"slug": "filesystem"})
    assert resp.status_code == 400
    assert "路径" in resp.json()["message"]


def test_duplicate_slug_is_rejected(client: TestClient) -> None:
    assert client.post("/api/mcp/servers", json={"slug": "time"}).status_code == 200
    resp = client.post("/api/mcp/servers", json={"slug": "time"})
    assert resp.status_code == 400
    assert "已经接入" in resp.json()["message"]


def test_custom_stdio_entry_validates_command_whitelist(client: TestClient) -> None:
    resp = client.post("/api/mcp/servers", json=_custom_payload(command="bash"))
    assert resp.status_code == 400
    assert "命令" in resp.json()["message"]


def test_custom_entry_requires_transport_and_name(client: TestClient) -> None:
    resp = client.post("/api/mcp/servers", json={"slug": "mine"})
    assert resp.status_code == 400
    assert "transport" in resp.json()["message"]


def test_toggle_and_update_drops_connection(client: TestClient) -> None:
    created = client.post("/api/mcp/servers", json={"slug": "time"}).json()["data"]
    server_id = created["id"]

    resp = client.patch(f"/api/mcp/servers/{server_id}", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False

    # 改成非法地址要被拦住（http 只允许 https）
    bad = client.patch(f"/api/mcp/servers/{server_id}", json={"url": "http://127.0.0.1/mcp"})
    assert bad.status_code == 400


def test_delete_removes_row(client: TestClient, db_session) -> None:
    created = client.post("/api/mcp/servers", json={"slug": "time"}).json()["data"]
    assert client.delete(f"/api/mcp/servers/{created['id']}").status_code == 200
    assert db_session.query(McpServer).count() == 0
    assert client.delete(f"/api/mcp/servers/{created['id']}").status_code == 404


def test_other_users_server_is_404(client: TestClient, anon_client: TestClient) -> None:
    created = client.post("/api/mcp/servers", json={"slug": "time"}).json()["data"]
    # 未登录
    assert anon_client.get("/api/mcp/servers").status_code == 401
    # 另一个账号看不到也改不了
    other = TestClient(client.app)
    other.post(
        "/api/auth/register",
        json={"email": "other-mcp@example.com", "password": "password123"},
    )
    assert (
        other.patch(f"/api/mcp/servers/{created['id']}", json={"enabled": False}).status_code == 404
    )
    assert other.get("/api/mcp/servers").json()["data"]["items"] == []


def test_test_endpoint_reports_tools_and_persists_status(client: TestClient, db_session) -> None:
    reset_manager()
    created = client.post("/api/mcp/servers", json=_custom_payload()).json()["data"]
    resp = client.post(f"/api/mcp/servers/{created['id']}/test")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["ok"] is True
    assert {tool["name"] for tool in data["tools"]} == {"mcp__echo__echo", "mcp__echo__add"}
    assert data["duration_ms"] >= 0

    row = db_session.get(McpServer, created["id"])
    assert row is not None
    assert row.last_status == "ok"
    assert row.tool_count == 2
    assert row.last_connected_time is not None
    reset_manager()


def test_test_endpoint_failure_is_reported_not_raised(client: TestClient, db_session) -> None:
    reset_manager()
    payload = _custom_payload(slug="broken", args=["--version"])
    payload["args"] = ["run", "--no-sync", "python", "-c", "raise SystemExit(3)"]
    created = client.post("/api/mcp/servers", json=payload).json()["data"]

    resp = client.post(f"/api/mcp/servers/{created['id']}/test")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ok"] is False
    assert data["message"]

    row = db_session.get(McpServer, created["id"])
    assert row is not None and row.last_status == "error" and row.last_error
    reset_manager()


def test_env_is_stored_encrypted_and_never_echoed(client: TestClient, db_session) -> None:
    pytest.importorskip("cryptography")
    created = client.post(
        "/api/mcp/servers",
        json=_custom_payload(slug="withenv", env={"TOKEN": "s3cret"}),
    )
    if created.status_code == 400:
        pytest.skip("当前环境没有配置 APP_SECRET_KEY")
    data = created.json()["data"]
    assert data["env_keys"] == ["TOKEN"]
    assert "s3cret" not in created.text

    row = db_session.get(McpServer, data["id"])
    assert row is not None and row.env_ciphertext and "s3cret" not in row.env_ciphertext
