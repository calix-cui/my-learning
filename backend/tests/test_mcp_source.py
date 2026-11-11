"""MCP 工具接入（阶段 7 T3）：适配成 `Tool`、装配进注册表、连接复用。

和 T1 一样，协议部分用真的 stdio server 验证；连接管理与装配这两层是纯本地逻辑，
用真实连接跑一遍比 mock 更能暴露「缓存键写错」「状态没落库」这类问题。
"""

from __future__ import annotations

import pathlib

import pytest
from sqlalchemy import select

from app.agent.executor import registry_for
from app.agent.tools.base import ToolLevel, meta_of, spec_of
from app.mcp import AsyncRunner, McpClient, McpServerSpec
from app.mcp.manager import McpManager, get_manager, reset_manager
from app.mcp.source import McpSource, tool_name
from app.models import McpServer

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "mcp_echo_server.py"


def _spec(slug: str = "echo") -> McpServerSpec:
    return McpServerSpec(
        slug=slug,
        display_name="Echo 服务器",
        transport="stdio",
        command="uv",
        args=("run", "--no-sync", "python", str(FIXTURE)),
    )


def _row(slug: str = "echo", *, enabled: bool = True) -> McpServer:
    """未入库的行对象：manager 只读它的属性，用不着数据库。"""
    return McpServer(
        id=hash(slug) % 10000,
        user_id=1,
        slug=slug,
        display_name="Echo 服务器",
        transport="stdio",
        command="uv",
        args=["run", "--no-sync", "python", str(FIXTURE)],
        enabled=enabled,
    )


@pytest.fixture(scope="module")
def runner():
    r = AsyncRunner()
    yield r
    r.close()


@pytest.fixture(scope="module")
def source(runner: AsyncRunner):
    client = McpClient(_spec(), runner)
    client.connect(timeout=60.0)
    tools = client.list_tools(timeout=30.0)
    yield McpSource(client, slug="echo", server_name="Echo 服务器", tools=tools)
    client.close()


def test_tools_are_prefixed_and_leveled(source: McpSource) -> None:
    tools = {tool.name: tool for tool in source.list()}
    assert set(tools) == {tool_name("echo", "echo"), tool_name("echo", "add")}
    assert tool_name("echo", "echo") == "mcp__echo__echo"
    # 没有 readOnlyHint 的外部工具一律 EXTERNAL：默认要用户确认
    assert tools["mcp__echo__echo"].level is ToolLevel.EXTERNAL
    assert source.name == "mcp:echo"
    assert source.tool_count == 2


def test_spec_passes_remote_schema_through(source: McpSource) -> None:
    tool = {t.name: t for t in source.list()}["mcp__echo__echo"]
    spec = spec_of(tool)
    assert spec["name"] == "mcp__echo__echo"
    assert "text" in spec["parameters"]["properties"]


def test_meta_marks_source_and_timeout(source: McpSource) -> None:
    tool = {t.name: t for t in source.list()}["mcp__echo__echo"]
    meta = meta_of(tool)
    assert meta.source == "mcp"
    assert meta.timeout_seconds == 10.0
    assert meta.requires_approval is True


def test_mcp_tool_runs_through_adapter(source: McpSource) -> None:
    tool = {t.name: t for t in source.list()}["mcp__echo__echo"]
    assert tool.run(tool.args_model.model_validate({"text": "你好"}), user_id=1) == "你好"


def test_iserror_becomes_tool_error(source: McpSource) -> None:
    """服务器抛异常时 `isError=true`，SDK 只回 `Error executing tool add`——细节不外泄。"""
    from app.agent.tools.base import ToolError

    tool = {t.name: t for t in source.list()}["mcp__echo__add"]
    with pytest.raises(ToolError, match="add"):
        tool.run(tool.args_model.model_validate({"a": -1, "b": 2}), user_id=1)


def test_manager_reuses_connection_and_closes_on_forget() -> None:
    manager = McpManager()
    row = _row("echo")
    try:
        first = manager.source_for(row)
        second = manager.source_for(row)
        # 同一条 server：复用连接与工具清单，不重复起子进程
        assert first._client is second._client
        assert manager.stats()["connections"] == 1

        manager.forget(row.id)
        assert manager.stats()["connections"] == 0
    finally:
        manager.close_all()


def test_sweep_reclaims_idle_connections() -> None:
    manager = McpManager()
    row = _row("echo")
    try:
        manager.source_for(row)
        assert manager.sweep(now=0.0) == 0
        assert manager.sweep(now=10**9) == 1
        assert manager.stats()["connections"] == 0
    finally:
        manager.close_all()


def test_registry_for_wires_enabled_servers(db_session, user) -> None:
    reset_manager()
    db_session.add(
        McpServer(
            user_id=user.id,
            slug="echo",
            display_name="Echo 服务器",
            transport="stdio",
            command="uv",
            args=["run", "--no-sync", "python", str(FIXTURE)],
        )
    )
    db_session.commit()

    registry = registry_for(db_session, user.id)
    assert "mcp__echo__echo" in registry.enabled_names()
    assert "mcp__echo__add" in registry.enabled_names()
    # 内置工具还在
    assert "calculator" in registry.enabled_names()

    row = db_session.scalar(select(McpServer).where(McpServer.user_id == user.id))
    assert row is not None
    assert row.last_status == "ok"
    assert row.tool_count == 2
    assert row.last_connected_time is not None
    reset_manager()


def test_registry_for_skips_disabled_server(db_session, user) -> None:
    reset_manager()
    db_session.add(
        McpServer(
            user_id=user.id,
            slug="echo",
            display_name="Echo 服务器",
            transport="stdio",
            command="uv",
            args=["run", "--no-sync", "python", str(FIXTURE)],
            enabled=False,
        )
    )
    db_session.commit()

    registry = registry_for(db_session, user.id)
    assert not any(name.startswith("mcp__") for name in registry.names())
    reset_manager()


def test_registry_for_records_connection_failure(db_session, user) -> None:
    """连不上只记状态，不打断对话——模型还能用内置工具。"""
    reset_manager()
    db_session.add(
        McpServer(
            user_id=user.id,
            slug="broken",
            display_name="坏服务器",
            transport="stdio",
            command="uv",
            args=["run", "--no-sync", "python", "-c", "raise SystemExit(3)"],
        )
    )
    db_session.commit()

    registry = registry_for(db_session, user.id)
    assert "calculator" in registry.enabled_names()
    row = db_session.scalar(select(McpServer).where(McpServer.slug == "broken"))
    assert row is not None and row.last_status == "error"
    assert row.last_error
    reset_manager()


def test_manager_singleton_is_shared() -> None:
    reset_manager()
    assert get_manager() is get_manager()
    reset_manager()
