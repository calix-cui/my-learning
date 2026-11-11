"""测试用的最小 MCP server（stdio 传输）。

跑法（测试里就是这么起的）：

    uv run python tests/fixtures/mcp_echo_server.py

暴露两个工具：
- `echo(text)`   原样返回，用来验证 `tools/call` 的文本回传；
- `add(a, b)`    故意在负数时抛错，用来验证 `isError` 的处理。
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

server = MCPServer(name="echo-fixture", version="0.1.0")


@server.tool()
def echo(text: str) -> str:
    """原样返回输入。"""
    return text


@server.tool()
def add(a: int, b: int) -> int:
    """两个非负数相加。"""
    if a < 0 or b < 0:
        raise ValueError("只支持非负数")
    return a + b


if __name__ == "__main__":
    server.run(transport="stdio")
