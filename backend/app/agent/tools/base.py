"""工具协议的公共部分：声明、结果、异常与执行入口。

约定（对应 `docs/agent.md` §3.3）：
- 工具**只读**，不接受写操作；
- 每个工具声明 JSON Schema，执行前用 pydantic 校验参数；
- 工具自己的失败要变成 `ToolResult(ok=False)` 回灌给模型，而不是抛给用户；
  只有「工具不存在」「参数不是合法 JSON」这类**协议级**错误才由注册表统一处理。
"""

import json
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, TypedDict

from pydantic import BaseModel, ValidationError


class ToolLevel(StrEnum):
    """工具的风险级别。决定「能不能直接跑」，也是审批的默认依据。

    - READ：只读本地数据，直接执行；
    - WRITE：写本地数据，默认要用户点一下；
    - EXTERNAL：出站访问外部服务，默认要用户点一下。
    """

    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"


# 级别 → 是否默认需要审批。READ 永远直跑，写/外网必须经人。
DEFAULT_APPROVAL: dict[ToolLevel, bool] = {
    ToolLevel.READ: False,
    ToolLevel.WRITE: True,
    ToolLevel.EXTERNAL: True,
}


@dataclass(frozen=True)
class ToolMeta:
    """工具的运行期元数据：执行器与策略层只认它，不认识具体工具。"""

    name: str
    description: str
    level: ToolLevel
    timeout_seconds: float = 2.0
    source: str = "builtin"
    requires_approval: bool = False

    @property
    def read_only(self) -> bool:
        return self.level is ToolLevel.READ


class ToolSpec(TypedDict):
    """给模型看的工具声明（OpenAI `tools[].function` 的形状）。"""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolResult(TypedDict):
    """一次工具执行的结果，直接作为 observation 回灌给模型。"""

    ok: bool
    content: str
    duration_ms: int
    args: dict[str, Any] | None
    error: str | None


class ToolError(Exception):
    """工具执行失败。会被执行器转成 `ToolResult(ok=False)`，不冒泡给用户。"""


class Tool(Protocol):
    """一个可被模型调用的工具。

    `level` 与 `timeout_seconds` 是可选的类属性：不声明就按只读、2 秒处理，
    这样老工具不用改一行就能接入注册表。
    """

    name: str
    description: str
    args_model: type[BaseModel]

    def run(self, args: BaseModel, *, user_id: int) -> str:
        """执行并返回给模型看的文本结果。`user_id` 用于数据隔离。"""
        ...

    def spec(self) -> ToolSpec: ...


def meta_of(tool: Tool, *, source: str = "builtin") -> ToolMeta:
    """从工具自身声明推导元数据；未声明的一律按最保守的默认值处理。"""
    level = getattr(tool, "level", ToolLevel.READ)
    if not isinstance(level, ToolLevel):
        level = ToolLevel(str(level))
    requires_approval = getattr(tool, "requires_approval", None)
    if requires_approval is None:
        requires_approval = DEFAULT_APPROVAL[level]
    return ToolMeta(
        name=tool.name,
        description=tool.description,
        level=level,
        timeout_seconds=float(getattr(tool, "timeout_seconds", 2.0)),
        source=str(getattr(tool, "source", source)),
        requires_approval=bool(requires_approval),
    )


def spec_of(tool: Tool) -> ToolSpec:
    """给模型的声明。

    内置工具由 pydantic 模型生成 JSON Schema（避免手写 schema 与校验不一致）；
    外部工具（MCP）带自己的 schema，用 `raw_spec()` 原样透传，避免往返走样。
    """
    raw = getattr(tool, "raw_spec", None)
    if callable(raw):
        return raw()
    return ToolSpec(
        name=tool.name,
        description=tool.description,
        parameters=tool.args_model.model_json_schema(),
    )


def parse_arguments(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """解析模型给的参数 JSON。返回 (参数, 错误信息)。"""
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return None, "工具参数不是合法 JSON"
    if not isinstance(value, dict):
        return None, "工具参数必须是 JSON 对象"
    return value, None


def validate_arguments(
    tool: Tool, raw: str
) -> tuple[BaseModel | None, dict[str, Any] | None, str | None]:
    """解析并校验参数。返回 (模型实例, 原始 dict, 错误信息)。"""
    data, error = parse_arguments(raw)
    if error is not None:
        return None, None, error
    assert data is not None
    try:
        return tool.args_model.model_validate(data), data, None
    except ValidationError as exc:
        # 只回灌第一条错误，避免把整段校验噪音塞进上下文
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "参数"
        return None, data, f"参数不正确：{field} {first['msg']}"


def run_tool(tool: Tool, raw_arguments: str, *, user_id: int) -> ToolResult:
    """执行一个工具，把任何异常都收敛成结果，保证循环不中断。"""
    started = time.perf_counter()
    model, data, error = validate_arguments(tool, raw_arguments)
    if error is not None:
        return ToolResult(
            ok=False,
            content=error,
            duration_ms=int((time.perf_counter() - started) * 1000),
            args=data,
            error=error,
        )

    assert model is not None
    try:
        content = tool.run(model, user_id=user_id)
    except ToolError as exc:
        return ToolResult(
            ok=False,
            content=str(exc),
            duration_ms=int((time.perf_counter() - started) * 1000),
            args=data,
            error=str(exc),
        )
    except Exception:
        return ToolResult(
            ok=False,
            content="工具执行出错",
            duration_ms=int((time.perf_counter() - started) * 1000),
            args=data,
            error="工具执行出错",
        )
    return ToolResult(
        ok=True,
        content=content,
        duration_ms=int((time.perf_counter() - started) * 1000),
        args=data,
        error=None,
    )
