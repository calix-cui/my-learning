"""Skill：一套可复用的「工作方法」。

与工具（`app/agent/tools/`）的分工：

- 工具回答「**能碰到什么**」——查库、读文件、调 MCP 服务器；
- 技能回答「**该怎么干**」——步骤、检查项、输出格式，以及这活该用哪些工具。

一个技能 = frontmatter 元数据 + Markdown 正文。内置技能放在
`app/skills/<slug>/SKILL.md`（随代码走、只读），用户自定义的存 `skills` 表。
"""

from app.skills.loader import builtin_skill, load_builtin_skills
from app.skills.models import (
    MAX_INSTRUCTIONS_CHARS,
    SKILL_SLUG_PATTERN,
    LoadedSkill,
    Skill,
    SkillDescriptor,
    SkillSummary,
    build_system_prompt,
)
from app.skills.providers import DatabaseSkillProvider, FileSystemSkillProvider
from app.skills.registry import SkillRegistry

__all__ = [
    "DatabaseSkillProvider",
    "FileSystemSkillProvider",
    "LoadedSkill",
    "MAX_INSTRUCTIONS_CHARS",
    "SKILL_SLUG_PATTERN",
    "Skill",
    "SkillDescriptor",
    "SkillRegistry",
    "SkillSummary",
    "build_system_prompt",
    "builtin_skill",
    "load_builtin_skills",
]
