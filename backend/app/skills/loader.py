"""内置技能的加载：读 `app/skills/<slug>/SKILL.md`，解析 frontmatter 与正文。

只做「读文件 + 校验」，不碰数据库。文件在导入时读一次，进程内缓存；
内置技能随代码发布，改完重启即生效（开发期 `--reload` 自动重载）。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.skills.models import (
    MAX_DESCRIPTION_CHARS,
    MAX_INSTRUCTIONS_CHARS,
    MAX_NAME_CHARS,
    MAX_TOOLS,
    SKILL_SLUG_PATTERN,
    SOURCE_BUILTIN,
    Skill,
)

SKILLS_DIR = Path(__file__).resolve().parent
SKILL_FILE = "SKILL.md"


class SkillFormatError(ValueError):
    """内置技能文件不合法。开发期直接在启动时炸掉，别让坏技能进上下文。"""


def _split_frontmatter(text: str, *, origin: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise SkillFormatError(f"{origin}: 缺少 frontmatter（文件应以 --- 开头）")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SkillFormatError(f"{origin}: frontmatter 没有闭合的 ---")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - 只有写坏 YAML 才走到
        raise SkillFormatError(f"{origin}: frontmatter 不是合法 YAML：{exc}") from exc
    if not isinstance(meta, dict):
        raise SkillFormatError(f"{origin}: frontmatter 必须是键值对")
    return meta, parts[2].strip()


def parse_skill(text: str, *, origin: str = "SKILL.md") -> Skill:
    """把一份 SKILL.md 解析成 `Skill`，顺手校验长度与 slug 规则。"""
    meta, body = _split_frontmatter(text, origin=origin)

    slug = str(meta.get("slug", "")).strip()
    if not SKILL_SLUG_PATTERN.match(slug):
        raise SkillFormatError(f"{origin}: slug 不合法（{slug!r}），只允许小写字母数字与连字符")

    name = str(meta.get("name", "")).strip()
    if not name or len(name) > MAX_NAME_CHARS:
        raise SkillFormatError(f"{origin}: name 必填且不超过 {MAX_NAME_CHARS} 字")

    description = str(meta.get("description", "")).strip()
    if not description or len(description) > MAX_DESCRIPTION_CHARS:
        raise SkillFormatError(f"{origin}: description 必填且不超过 {MAX_DESCRIPTION_CHARS} 字")

    if not body:
        raise SkillFormatError(f"{origin}: 正文不能为空")
    if len(body) > MAX_INSTRUCTIONS_CHARS:
        raise SkillFormatError(f"{origin}: 正文超过 {MAX_INSTRUCTIONS_CHARS} 字")

    raw_tools = meta.get("tools") or []
    if not isinstance(raw_tools, list):
        raise SkillFormatError(f"{origin}: tools 必须是列表")
    tools = tuple(str(item).strip() for item in raw_tools if str(item).strip())
    if len(tools) > MAX_TOOLS:
        raise SkillFormatError(f"{origin}: tools 最多 {MAX_TOOLS} 个")

    return Skill(
        slug=slug,
        name=name,
        description=description,
        instructions=body,
        tools=tools,
        icon=str(meta.get("icon", "sparkle")).strip() or "sparkle",
        source=SOURCE_BUILTIN,
    )


def load_builtin_skills(directory: Path | None = None) -> dict[str, Skill]:
    """扫描目录下的 `<slug>/SKILL.md`。目录不存在时返回空表（打包场景容错）。"""
    root = directory or SKILLS_DIR
    skills: dict[str, Skill] = {}
    if not root.is_dir():  # pragma: no cover - 正常安装不会缺目录
        return skills
    for path in sorted(root.glob(f"*/{SKILL_FILE}")):
        skill = parse_skill(path.read_text(encoding="utf-8"), origin=str(path))
        if skill.slug in skills:  # pragma: no cover - 目录名唯一，防手滑
            raise SkillFormatError(f"内置技能 slug 重复：{skill.slug}")
        skills[skill.slug] = skill
    return skills


BUILTIN_SKILLS: dict[str, Skill] = load_builtin_skills()


def builtin_skill(slug: str) -> Skill | None:
    return BUILTIN_SKILLS.get(slug)
