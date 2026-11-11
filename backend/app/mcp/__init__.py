"""MCP 适配层：把 MCP server 的工具装成阶段 6 的 `ToolSource`。

对外三件事：`McpClient`（连接 / 列工具 / 调工具）、`AsyncRunner`（同步桥）、
`McpServerSpec`（服务器描述）；再加上 T3 的 `McpSource`（装配成 `ToolSource`）与
`get_manager()`（跨请求复用连接）。`agent/` 不认识 MCP，只认识 `ToolSource`。
"""

from app.mcp.client import McpClient
from app.mcp.errors import McpError
from app.mcp.manager import get_manager, probe
from app.mcp.runner import AsyncRunner
from app.mcp.source import McpSource, McpTool, tool_name
from app.mcp.specs import McpCallResult, McpServerSpec, McpToolInfo

__all__ = [
    "AsyncRunner",
    "McpCallResult",
    "McpClient",
    "McpError",
    "McpServerSpec",
    "McpSource",
    "McpTool",
    "McpToolInfo",
    "get_manager",
    "probe",
    "tool_name",
]
