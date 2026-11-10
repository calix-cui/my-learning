"""注册表单测：加工具不改执行器、重名报错、关掉的工具既不展示也调不动。"""

from typing import Any

import pytest
from pydantic import BaseModel

from app.agent.tools import ToolLevel, ToolRegistry
from app.agent.tools.base import ToolSpec, meta_of, spec_of


class _Args(BaseModel):
    pass


class _FakeTool:
    name = "fake_echo"
    description = "回显参数，用来验证「加工具不改执行器」"
    args_model = _Args
    level = ToolLevel.READ

    def run(self, args: BaseModel, *, user_id: int) -> str:  # noqa: ARG002
        return "echo"

    def spec(self) -> ToolSpec:
        return spec_of(self)


def test_new_tool_only_needs_a_class():
    registry = ToolRegistry([_FakeTool()])
    assert registry.has("fake_echo")
    assert [spec["name"] for spec in registry.specs()] == ["fake_echo"]
    assert registry.execute("fake_echo", "{}", user_id=1)["ok"] is True


def test_duplicate_names_raise_instead_of_silently_overriding():
    with pytest.raises(ValueError, match="工具名重复"):
        ToolRegistry([_FakeTool(), _FakeTool()])


def test_disabled_tool_is_hidden_from_specs_and_refuses_to_run():
    registry = ToolRegistry([_FakeTool()], disabled={"fake_echo"})
    assert registry.specs() == []
    assert registry.has("fake_echo") is True
    result = registry.execute("fake_echo", "{}", user_id=1)
    assert result["ok"] is False
    assert "未启用" in result["content"]


def test_unknown_tool_returns_result_not_exception():
    registry = ToolRegistry([_FakeTool()])
    result = registry.execute("nope", "{}", user_id=1)
    assert result["ok"] is False
    assert "没有名为 nope" in result["content"]


def test_meta_derives_level_and_approval_from_declaration():
    assert meta_of(_FakeTool()).level is ToolLevel.READ
    assert meta_of(_FakeTool()).requires_approval is False

    class _Writer(_FakeTool):
        name = "writer"
        level = ToolLevel.WRITE

    meta: Any = meta_of(_Writer())
    assert meta.level is ToolLevel.WRITE
    assert meta.requires_approval is True
