"""策略层单测：读直跑、写挂起、黑名单直拒、配额与审批上限。"""

from typing import Any

from pydantic import BaseModel

from app.agent.policy import (
    DEFAULT_DAILY_TOOL_BUDGET,
    MAX_APPROVALS_PER_RUN,
    MAX_REJECTS_PER_TOOL,
    ToolPolicy,
)
from app.agent.tools import ToolLevel, ToolRegistry
from app.agent.tools.base import ToolSpec, spec_of


class _EmptyArgs(BaseModel):
    pass


class _StubTool:
    """只用来验证元数据推导与策略判断，不真正执行。"""

    def __init__(self, name: str, level: ToolLevel) -> None:
        self.name = name
        self.description = f"stub {name}"
        self.args_model = _EmptyArgs
        self.level = level

    def run(self, args: BaseModel, *, user_id: int) -> str:  # noqa: ARG002
        return "ok"

    def spec(self) -> dict[str, Any]:
        return spec_of(self)


def _registry(*tools: _StubTool, disabled: tuple[str, ...] = ()) -> ToolRegistry:
    return ToolRegistry(list(tools), disabled=disabled)


def test_read_tool_runs_without_approval():
    policy = ToolPolicy(_registry(_StubTool("clock", ToolLevel.READ)))
    assert policy.check("clock", {}).allowed


def test_write_and_external_tools_need_approval():
    policy = ToolPolicy(
        _registry(_StubTool("rename", ToolLevel.WRITE), _StubTool("fetch", ToolLevel.EXTERNAL))
    )
    assert policy.check("rename", {}).needs_approval
    assert policy.check("fetch", {}).needs_approval


def test_disabled_tool_is_denied_not_approved():
    policy = ToolPolicy(
        _registry(_StubTool("rename", ToolLevel.WRITE), disabled=("rename",)),
        disabled=frozenset({"rename"}),
    )
    decision = policy.check("rename", {})
    assert decision.action == "deny"
    assert "未启用" in decision.reason


def test_param_rule_denies_big_exponent_without_approval_gate():
    policy = ToolPolicy(_registry(_StubTool("calculator", ToolLevel.READ)))
    decision = policy.check("calculator", {"expression": "9**30"})
    assert decision.action == "deny"
    assert "指数" in decision.reason
    # 安全范围内的表达式仍然直跑
    assert policy.check("calculator", {"expression": "3**5"}).allowed


def test_daily_budget_is_enforced():
    policy = ToolPolicy(
        _registry(_StubTool("clock", ToolLevel.READ)),
        daily_budget=DEFAULT_DAILY_TOOL_BUDGET,
        daily_used=DEFAULT_DAILY_TOOL_BUDGET,
    )
    decision = policy.check("clock", {})
    assert decision.action == "deny"
    assert "上限" in decision.reason


def test_approval_count_and_reject_limits():
    policy = ToolPolicy(
        _registry(_StubTool("rename", ToolLevel.WRITE)),
        approvals_used=MAX_APPROVALS_PER_RUN,
    )
    assert policy.check("rename", {}).action == "deny"

    policy = ToolPolicy(
        _registry(_StubTool("rename", ToolLevel.WRITE)),
        rejects_by_tool={"rename": MAX_REJECTS_PER_TOOL},
    )
    decision = policy.check("rename", {})
    assert decision.action == "deny"
    assert "拒绝" in decision.reason


def test_unknown_tool_is_denied():
    policy = ToolPolicy(_registry(_StubTool("clock", ToolLevel.READ)))
    assert policy.check("nope", {}).action == "deny"
