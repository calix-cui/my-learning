"""把 MCP 工具包装成 app 内的 `Tool`。

命名规则是 `mcp__{slug}__{tool}`（`docs/mcp.md` §4）：slug 进名字，提示词里也看得见
「这是哪个服务器给的」，两个服务器有同名工具时不会互相覆盖（注册表遇到重名会直接报错）。

三个刻意的取舍：
- **级别不猜**：MCP 的 `readOnlyHint` 只用来**降级**到 READ；没有这个标注一律按
  EXTERNAL（出站访问外部服务），默认要用户确认。
- **schema 透传**：参数声明用服务器给的原样 JSON Schema，不用 pydantic 重新生成，
  否则 enum / oneOf / 嵌套对象会在往返中走样。校验交给服务器，我们只负责传。
- **超时 10 秒**：内置工具 2 秒，外部工具要等网络与子进程，给到 10 秒。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agent.tools.base import ToolError, ToolLevel, ToolSpec
from app.mcp.client import McpClient
from app.mcp.specs import McpToolInfo

PREFIX = "mcp__"
MCP_TOOL_TIMEOUT_SECONDS = 10.0


def tool_name(slug: str, remote_name: str) -> str:
    """给模型看的名字：`mcp__filesystem__read_file`。"""
    return f"{PREFIX}{slug}__{remote_name}"


class McpArgs(BaseModel):
    """任意参数都放行：真正的校验在 MCP server 那边。"""

    model_config = ConfigDict(extra="allow")


class McpTool:
    """一个远端工具在本地的投影。"""

    args_model = McpArgs
    level: ToolLevel
    timeout_seconds = MCP_TOOL_TIMEOUT_SECONDS
    source = "mcp"

    def __init__(
        self,
        client: McpClient,
        *,
        slug: str,
        server_name: str,
        info: McpToolInfo,
    ) -> None:
        self._client = client
        self._slug = slug
        self._server_name = server_name
        self._info = info
        self._remote_name = info.name
        self.name = tool_name(slug, info.name)
        self.description = (
            f"{server_name} · {info.description}" if info.description else server_name
        )
        # 服务器声明「只读」才降级为 READ；其余一律 EXTERNAL，默认走审批
        self.level = ToolLevel.READ if info.read_only else ToolLevel.EXTERNAL

    def raw_spec(self) -> ToolSpec:
        """原样透传服务器的 input schema（注册表会优先用它）。"""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self._info.input_schema,
        )

    def run(self, args: BaseModel, *, user_id: int) -> str:
        # 远端工具自己决定怎么用参数；`user_id` 由本地内置工具用来做数据隔离
        del user_id
        payload = args.model_dump()
        result = self._client.call_tool(self._remote_name, payload or None)
        if not result.ok:
            # `isError` 是工具自己报告的业务失败，按 ToolError 交给执行器转成 ok=False
            raise ToolError(result.text or "工具返回了错误")
        return result.text or "（工具没有返回文本内容）"


class McpSource:
    """一台 MCP server 提供的全部工具。"""

    def __init__(
        self,
        client: McpClient,
        *,
        slug: str,
        server_name: str,
        tools: list[McpToolInfo],
    ) -> None:
        self._client = client
        self._slug = slug
        self._server_name = server_name
        self._infos = tools
        self.name = f"mcp:{slug}"

    def list(self) -> list[McpTool]:
        return [
            McpTool(
                self._client,
                slug=self._slug,
                server_name=self._server_name,
                info=info,
            )
            for info in self._infos
        ]

    @property
    def tool_count(self) -> int:
        return len(self._infos)

    def names(self) -> list[str]:
        return [tool_name(self._slug, info.name) for info in self._infos]

    def describe(self) -> list[dict[str, Any]]:
        """给接口/前端用的清单（不含函数体）。"""
        return [
            {
                "name": tool_name(self._slug, info.name),
                "remote_name": info.name,
                "description": info.description,
                "read_only": info.read_only,
            }
            for info in self._infos
        ]


__all__ = [
    "MCP_TOOL_TIMEOUT_SECONDS",
    "PREFIX",
    "McpArgs",
    "McpSource",
    "McpTool",
    "tool_name",
]
