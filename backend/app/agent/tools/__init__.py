"""工具注册表：把「有哪些工具」集中在一处，执行器只认这里的名字。

新增工具 = 写一个类 + 在 `build_registry()` 里加一行，不用改执行器。
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.agent.tools.base import Tool, ToolError, ToolResult, ToolSpec, run_tool, spec_of
from app.agent.tools.calculator import CalculatorTool
from app.agent.tools.clock import NowTool
from app.agent.tools.history import SearchConversationsTool

__all__ = [
    "Tool",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "build_registry",
]

# 需要数据库会话的工具用工厂描述；不需要的直接给类
ToolFactory = Callable[[Session], Tool]


def build_registry(session: Session) -> "ToolRegistry":
    """按当前请求构造注册表（`search_conversations` 需要会话）。"""
    tools: list[Tool] = [CalculatorTool(), NowTool(), SearchConversationsTool(session)]
    return ToolRegistry(tools)


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def specs(self) -> list[ToolSpec]:
        return [spec_of(tool) for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def has(self, name: str) -> bool:
        return name in self._tools

    def execute(self, name: str, raw_arguments: str, *, user_id: int) -> ToolResult:
        """按名字执行；未注册的工具也返回结果而不是抛错，交给模型处理。"""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                content=f"没有名为 {name} 的工具",
                duration_ms=0,
                args=None,
                error=f"unknown tool: {name}",
            )
        return run_tool(tool, raw_arguments, user_id=user_id)
