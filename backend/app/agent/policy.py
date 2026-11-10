"""工具策略层：这次调用能不能直接跑。

三层判断，顺序不能换（对应 `docs/tools.md` §3.3）：

1. 工具被用户关掉 → 直接拒；
2. 命中参数黑名单 / 超出配额 → 直接拒（不进审批，避免「点一下就能过」）；
3. 按级别决定：只读直跑，写/外网挂起等审批。

规则用数据描述而不是写死在 if 里：以后加一条黑名单只改 `DEFAULT_RULES`。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.agent.tools import ToolRegistry

# 单次运行的审批总量与「同一工具被拒次数」上限：防模型换个参数接着试
MAX_APPROVALS_PER_RUN = 5
MAX_REJECTS_PER_TOOL = 2

# 每用户每日工具调用上限
DEFAULT_DAILY_TOOL_BUDGET = 500

DecisionAction = Literal["allow", "deny", "approve"]


@dataclass(frozen=True)
class Decision:
    """策略结论。`deny` 会直接变成 `ok=false` 的工具结果回灌给模型。"""

    action: DecisionAction
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.action == "allow"

    @property
    def needs_approval(self) -> bool:
        return self.action == "approve"


@dataclass(frozen=True)
class ParamRule:
    """按参数拒绝的规则：`tool` + 参数名（只支持顶层键，够用且好写）。"""

    tool: str
    path: str
    deny_pattern: str | None = None
    max_value: float | None = None
    reason: str = "参数不符合安全规则"


# 默认规则：都是「模型能自己调整到安全范围」的软拒绝，不是安全边界的替代品
DEFAULT_RULES: tuple[ParamRule, ...] = (
    ParamRule(
        tool="calculator",
        path="expression",
        # 指数 ≥ 30 直接拒：大数幂会吃满 CPU（9**9**9 那类已经由工具自身拦住）
        deny_pattern=r"\*\*\s*(?:[3-9]\d|\d{3,})",
        reason="指数太大，请改用不超过 20 的指数",
    ),
    ParamRule(
        tool="search_conversations",
        path="limit",
        max_value=10,
        reason="最多一次查 10 条",
    ),
)


@dataclass
class ToolPolicy:
    """一次运行内的策略：用户设置 + 配额 + 规则。"""

    registry: ToolRegistry
    disabled: frozenset[str] = frozenset()
    daily_budget: int = DEFAULT_DAILY_TOOL_BUDGET
    daily_used: int = 0
    rules: tuple[ParamRule, ...] = DEFAULT_RULES
    # 运行内计数由执行器维护，策略层只读来判断「还能不能再弹一次审批」
    approvals_used: int = 0
    rejects_by_tool: dict[str, int] = field(default_factory=dict)

    def check(self, name: str, arguments: dict[str, Any] | None) -> Decision:
        meta = self.registry.meta(name)
        if meta is None:
            return Decision("deny", f"没有名为 {name} 的工具")
        if name in self.disabled or not self.registry.is_enabled(name):
            return Decision("deny", f"工具 {name} 未启用：用户已在设置里关闭它")
        if self.daily_used >= self.daily_budget:
            return Decision("deny", f"今日工具调用已达上限（{self.daily_budget} 次）")

        violated = self._match_rule(name, arguments)
        if violated is not None:
            return Decision("deny", violated)

        if meta.requires_approval:
            if self.approvals_used >= MAX_APPROVALS_PER_RUN:
                return Decision("deny", f"本次运行审批次数已达上限（{MAX_APPROVALS_PER_RUN} 次）")
            if self.rejects_by_tool.get(name, 0) >= MAX_REJECTS_PER_TOOL:
                return Decision("deny", f"工具 {name} 已被拒绝 {MAX_REJECTS_PER_TOOL} 次，已中止")
            return Decision("approve", f"{name} 是 {meta.level} 级工具，需要你确认")
        return Decision("allow")

    def _match_rule(self, name: str, arguments: dict[str, Any] | None) -> str | None:
        for rule in self.rules:
            if rule.tool != name:
                continue
            value = (arguments or {}).get(rule.path)
            if rule.deny_pattern and isinstance(value, str):
                if re.search(rule.deny_pattern, value):
                    return rule.reason
            if rule.max_value is not None and isinstance(value, (int, float)):
                if value > rule.max_value:
                    return rule.reason
        return None


__all__ = [
    "DEFAULT_DAILY_TOOL_BUDGET",
    "DEFAULT_RULES",
    "MAX_APPROVALS_PER_RUN",
    "MAX_REJECTS_PER_TOOL",
    "Decision",
    "ParamRule",
    "ToolPolicy",
]
