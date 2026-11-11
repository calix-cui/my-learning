"""技能的数据形状：内置与自定义共用一份，接口层只认它。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 与工具名、MCP slug 保持同一套字符规则：小写字母数字与连字符，最长 32
SKILL_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")

MAX_NAME_CHARS = 30
MAX_DESCRIPTION_CHARS = 120
# 与消息上限一致：正文会整体进 system prompt，太长会拖慢首字
MAX_INSTRUCTIONS_CHARS = 4000
MAX_TOOLS = 20

SOURCE_BUILTIN = "builtin"
SOURCE_CUSTOM = "custom"


@dataclass(frozen=True)
class Skill:
    """一个完整的技能（含正文）。"""

    slug: str
    name: str
    description: str
    instructions: str
    tools: tuple[str, ...] = ()
    icon: str = "sparkle"
    source: str = SOURCE_BUILTIN
    skill_id: int | None = None

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    def summary(self) -> SkillSummary:
        """选择器与列表页只需要元数据，不需要把正文传出去。"""
        return SkillSummary(
            slug=self.slug,
            name=self.name,
            description=self.description,
            tools=self.tools,
            icon=self.icon,
            source=self.source,
            skill_id=self.skill_id,
        )


@dataclass(frozen=True)
class SkillSummary:
    """不带正文的技能元数据。"""

    slug: str
    name: str
    description: str
    tools: tuple[str, ...] = field(default_factory=tuple)
    icon: str = "sparkle"
    source: str = SOURCE_BUILTIN
    skill_id: int | None = None

    @property
    def tool_count(self) -> int:
        return len(self.tools)


def build_system_prompt(skill: Skill, *, tool_names: list[str]) -> str:
    """把技能拼成一条 system 消息。

    三条规矩：
    1. 正文原样拼接，不改写——文档写什么就执行什么；
    2. 列清楚当前能用的工具，免得模型对着不存在的工具空想；
    3. 提醒审批规则，写操作被拒时不要原样重试。
    """
    lines = [
        "你是 My Agent，一个能调用工具的个人助手。回答用中文，除非用户用别的语言提问。",
        f"当前技能：{skill.name}",
        "",
        skill.instructions.strip(),
        "",
    ]
    if skill.tools:
        lines.append("本次对话只开放这些工具：" + "、".join(tool_names or skill.tools) + "。")
    else:
        lines.append("本次对话可用的工具：" + "、".join(tool_names) + "。")
    lines.append(
        "写操作与外部工具每次调用前都会请用户确认；被拒绝时按用户给的理由调整，不要重试同一个调用。"
    )
    return "\n".join(lines)
