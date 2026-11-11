"""阶段 7 T2：内置市场清单与 `mcp_servers` 模型。

清单的测试价值在于「不让人手滑写坏一条」：命令不在白名单、远程地址不是 https、
占位符漏写 `{path}`，这些都会在发布前被抓到，而不是等用户点「接入」时报错。
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.mcp.catalog import CATALOG, catalog_slugs, find_entry
from app.mcp.errors import McpError
from app.mcp.specs import ALLOWED_COMMANDS, McpServerSpec
from app.models import McpServer, User


def test_catalog_slugs_unique_and_lookup_works() -> None:
    slugs = [entry.slug for entry in CATALOG]
    assert len(slugs) == len(set(slugs))
    assert catalog_slugs() == tuple(slugs)
    assert find_entry("not-exist") is None


def test_every_entry_produces_a_valid_spec() -> None:
    for entry in CATALOG:
        path = "/tmp/workspace" if entry.requires_path else None
        spec = entry.build_spec(path=path)
        assert spec.slug == entry.slug
        assert spec.transport == entry.transport
        if entry.transport == "stdio":
            assert spec.command in ALLOWED_COMMANDS
        else:
            assert spec.url and spec.url.startswith("https://")


def test_entries_requiring_path_refuse_to_build_without_it() -> None:
    entry = find_entry("git")
    assert entry is not None and entry.requires_path
    with pytest.raises(ValueError, match="需要一个目录或文件路径"):
        entry.build_spec()


def test_stdio_entries_declare_path_placeholder() -> None:
    for entry in CATALOG:
        if entry.requires_path:
            assert any("{path}" in arg for arg in entry.args), entry.slug


def test_create_server_defaults_and_unique_slug(db_session, user) -> None:
    server = McpServer(
        user_id=user.id,
        slug="fetch",
        display_name="网页抓取",
        transport="stdio",
        command="uvx",
        args=["mcp-server-fetch"],
    )
    db_session.add(server)
    db_session.commit()
    db_session.refresh(server)

    assert server.enabled is True
    assert server.last_status == "unknown"
    assert server.tool_count == 0
    assert server.spec_payload["args"] == ("mcp-server-fetch",)

    db_session.add(
        McpServer(
            user_id=user.id,
            slug="fetch",
            display_name="另一个",
            transport="stdio",
            command="uvx",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_user_cascades_servers(db_session, user) -> None:
    db_session.add(
        McpServer(
            user_id=user.id,
            slug="time",
            display_name="时间",
            transport="stdio",
            command="uvx",
        )
    )
    db_session.commit()
    assert db_session.query(McpServer).count() == 1

    db_session.delete(db_session.get(User, user.id))
    db_session.commit()
    assert db_session.query(McpServer).count() == 0


def test_spec_rejects_hostile_command_from_user_input() -> None:
    """用户自定义条目也要过白名单——这是「别把远程执行入口写进配置」的兜底。"""
    with pytest.raises(McpError):
        McpServerSpec(slug="custom", display_name="自定义", transport="stdio", command="bash")
