"""工具注册表：加工具不改循环。

三层结构（对应 `docs/tools.md` §3.2）：

    ToolSource(协议) ──> list() -> list[Tool]
       ├── BuiltinSource   内置工具（本阶段三个只读工具）
       └── McpSource       阶段 7 的 MCP 适配（这里只留协议，不连真 server）

    ToolRegistry
       ├── 装配：遍历所有 source，重名直接报错（不静默覆盖）
       ├── 过滤：按用户设置剔除 disabled 的工具（模型看不到、也调不动）
       ├── 暴露：specs() 给模型、has() 给执行器、execute() 统一兜异常与超时
       └── 元数据：meta() 给策略层判级

执行器只认这三件事，所以「新增一种工具」= 写一个类 + 注册进某个 source，
不用改 `executor.py`。
"""

from collections.abc import Iterable
from typing import Protocol

from sqlalchemy.orm import Session

from app.agent.tools.base import (
    Tool,
    ToolError,
    ToolLevel,
    ToolMeta,
    ToolResult,
    ToolSpec,
    meta_of,
    run_tool,
    spec_of,
)
from app.agent.tools.calculator import CalculatorTool
from app.agent.tools.clock import NowTool
from app.agent.tools.conversation import RenameConversationTool
from app.agent.tools.history import SearchConversationsTool

__all__ = [
    "BuiltinSource",
    "Tool",
    "ToolError",
    "ToolLevel",
    "ToolMeta",
    "ToolRegistry",
    "ToolResult",
    "ToolSource",
    "ToolSpec",
    "build_registry",
]


class ToolSource(Protocol):
    """一组同源工具（内置 / MCP / 未来的插件）。"""

    name: str

    def list(self) -> list[Tool]: ...


class BuiltinSource:
    """内置工具。需要数据库会话的用构造参数传，不靠全局变量。"""

    name = "builtin"

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[Tool]:
        return [
            CalculatorTool(),
            NowTool(),
            SearchConversationsTool(self._session),
            RenameConversationTool(self._session),
        ]


def build_registry(session: Session, *, disabled: Iterable[str] = ()) -> "ToolRegistry":
    """按当前请求构造注册表；`disabled` 来自用户设置，被关掉的工具既不展示也执行不了。"""
    return ToolRegistry.from_sources([BuiltinSource(session)], disabled=disabled)


class ToolRegistry:
    """装配好的工具集合。同一时刻一个请求一个实例。"""

    def __init__(self, tools: Iterable[Tool], *, disabled: Iterable[str] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        self._metas: dict[str, ToolMeta] = {}
        for tool in tools:
            if tool.name in self._tools:
                # 重名说明两个 source 想抢同一个名字，静默覆盖会让「谁生效」变得不可预测
                raise ValueError(f"工具名重复：{tool.name}")
            self._tools[tool.name] = tool
            self._metas[tool.name] = meta_of(tool)
        self._disabled = set(disabled)

    @classmethod
    def from_sources(
        cls, sources: Iterable[ToolSource], *, disabled: Iterable[str] = ()
    ) -> "ToolRegistry":
        tools: list[Tool] = []
        for source in sources:
            tools.extend(source.list())
        return cls(tools, disabled=disabled)

    # ---- 读 ----

    def names(self) -> list[str]:
        """全部已注册的工具名（含被关闭的），给设置页展示用。"""
        return list(self._tools)

    def enabled_names(self) -> list[str]:
        return [name for name in self._tools if name not in self._disabled]

    def has(self, name: str) -> bool:
        """是否注册过（不判断是否启用：启用与否在执行时给出明确原因）。"""
        return name in self._tools

    def is_enabled(self, name: str) -> bool:
        return name in self._tools and name not in self._disabled

    def meta(self, name: str) -> ToolMeta | None:
        return self._metas.get(name)

    def metas(self) -> list[ToolMeta]:
        return [self._metas[name] for name in self._tools]

    def specs(self) -> list[ToolSpec]:
        """给模型的工具声明：被用户关掉的不出现，省 token 也少误调。"""
        return [spec_of(self._tools[name]) for name in self.enabled_names()]

    # ---- 执行 ----

    def execute(self, name: str, raw_arguments: str, *, user_id: int) -> ToolResult:
        """按名字执行；不抛异常，所有失败都变成 `ToolResult(ok=False)` 交给模型。"""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                content=f"没有名为 {name} 的工具",
                duration_ms=0,
                args=None,
                error=f"unknown tool: {name}",
            )
        if name in self._disabled:
            return ToolResult(
                ok=False,
                content=f"工具 {name} 未启用：用户已在设置里关闭它，换个办法或直接回答",
                duration_ms=0,
                args=None,
                error="tool disabled",
            )
        return run_tool(tool, raw_arguments, user_id=user_id)
