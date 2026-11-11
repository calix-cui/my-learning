"""MCP 客户端（阶段 7 T1）的行为测试。

策略：
- 协议正确性用**真的 stdio server** 验证（`tests/fixtures/mcp_echo_server.py`，用官方 SDK 起的），
  而不是 mock——mock 只能证明「我以为协议是这样」；
- 同步桥 `AsyncRunner` 一并被覆盖，因为测试本身就是通过它调用的。
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest

from app.mcp import AsyncRunner, McpClient, McpError, McpServerSpec
from app.mcp.errors import McpErrorKind

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "mcp_echo_server.py"


def _fixture_spec() -> McpServerSpec:
    return McpServerSpec(
        slug="fixture",
        display_name="Echo Fixture",
        transport="stdio",
        command="uv",
        # --no-sync：直接用现有 .venv，测试里不要再解析一次依赖
        args=("run", "--no-sync", "python", str(FIXTURE)),
    )


@pytest.fixture(scope="module")
def runner():
    r = AsyncRunner()
    yield r
    r.close()


@pytest.fixture(scope="module")
def client(runner: AsyncRunner):
    c = McpClient(_fixture_spec(), runner)
    c.connect(timeout=60.0)
    yield c
    c.close()


# ---------- 配置校验：不连服务器就能拦住 ----------


def test_rejects_command_outside_allowlist() -> None:
    with pytest.raises(McpError) as exc:
        McpServerSpec(slug="bad", display_name="bad", transport="stdio", command="rm")
    assert exc.value.kind == McpErrorKind.CONFIG
    assert "启动命令只允许" in exc.value.message


def test_rejects_plain_http_and_private_hosts() -> None:
    for url in ("http://example.com/mcp", "https://127.0.0.1/mcp", "https://localhost/mcp"):
        with pytest.raises(McpError) as exc:
            McpServerSpec(slug="bad", display_name="bad", transport="http", url=url)
        assert exc.value.kind == McpErrorKind.CONFIG


def test_stdio_requires_command_and_http_requires_url() -> None:
    with pytest.raises(McpError):
        McpServerSpec(slug="x", display_name="x", transport="stdio")
    with pytest.raises(McpError):
        McpServerSpec(slug="x", display_name="x", transport="http")


def test_slug_pattern() -> None:
    with pytest.raises(McpError):
        McpServerSpec(slug="Bad Slug", display_name="x", transport="stdio", command="uvx")


# ---------- 真连接 ----------


def test_list_tools(client: McpClient) -> None:
    tools = client.list_tools()
    by_name = {tool.name: tool for tool in tools}
    assert {"echo", "add"} <= set(by_name)
    properties = by_name["echo"].input_schema.get("properties", {})
    assert "text" in properties


def test_call_tool_returns_text(client: McpClient) -> None:
    result = client.call_tool("echo", {"text": "hello mcp"})
    assert result.ok is True
    assert result.text == "hello mcp"


def test_call_tool_error_is_not_exception(client: McpClient) -> None:
    result = client.call_tool("add", {"a": -1, "b": 2})
    assert result.ok is False
    assert "Error executing" in result.text


# ---------- 失败路径 ----------


def test_connect_failure_maps_to_connect_error(runner: AsyncRunner) -> None:
    spec = McpServerSpec(
        slug="broken",
        display_name="Broken",
        transport="stdio",
        command="python3",
        args=("-c", "raise SystemExit(1)"),
    )
    broken = McpClient(spec, runner)
    with pytest.raises(McpError) as exc:
        broken.connect(timeout=20.0)
    assert exc.value.kind in (McpErrorKind.CONNECT, McpErrorKind.TIMEOUT)


def test_runner_timeout(runner: AsyncRunner) -> None:
    with pytest.raises(McpError) as exc:
        runner.submit(asyncio.sleep(3), timeout=0.2)
    assert exc.value.kind == McpErrorKind.TIMEOUT
