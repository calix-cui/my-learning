"""内置技能的加载：读 `app/skills/<slug>/SKILL.md`，解析 frontmatter 与正文。

只做「读文件 + 校验」，不碰数据库、不保留导入时的正文缓存；目录扫描由请求级
Skill Provider 发起，完整正文只在显式加载时返回。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.skills.models import (
    MAX_TOOLS,
    SKILL_SLUG_PATTERN,
    SOURCE_BUILTIN,
    Skill,
    SkillSummary,
)

SKILLS_DIR = Path(__file__).resolve().parent
SKILL_FILE = "SKILL.md"
MAX_SKILL_FILE_BYTES = 65_536
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024
MAX_INSTRUCTIONS_CHARS = 12_000


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


def _metadata_fields(
    meta: dict, *, origin: str, default_slug: str | None = None
) -> tuple[str, str, str, tuple[str, ...], str]:
    for key in ("slug", "name", "description", "icon"):
        if key in meta and not isinstance(meta[key], str):
            raise SkillFormatError(f"{origin}: {key} 必须是文本")
    slug = str(meta.get("slug", default_slug or "")).strip()
    if not SKILL_SLUG_PATTERN.match(slug):
        raise SkillFormatError(f"{origin}: slug 不合法（{slug!r}），只允许小写字母数字与连字符")

    name = str(meta.get("name", "")).strip()
    if not name or len(name) > MAX_NAME_CHARS:
        raise SkillFormatError(f"{origin}: name 必填且不超过 {MAX_NAME_CHARS} 字")

    description = str(meta.get("description", "")).strip()
    if not description or len(description) > MAX_DESCRIPTION_CHARS:
        raise SkillFormatError(f"{origin}: description 必填且不超过 {MAX_DESCRIPTION_CHARS} 字")

    raw_tools = meta.get("tools", [])
    if not isinstance(raw_tools, list) or any(not isinstance(item, str) for item in raw_tools):
        raise SkillFormatError(f"{origin}: tools 必须是列表")
    tools = tuple(str(item).strip() for item in raw_tools if str(item).strip())
    if len(tools) > MAX_TOOLS:
        raise SkillFormatError(f"{origin}: tools 最多 {MAX_TOOLS} 个")

    icon = str(meta.get("icon", "sparkle")).strip() or "sparkle"
    return slug, name, description, tools, icon


def parse_skill_metadata(
    text: str, *, origin: str = "SKILL.md", default_slug: str | None = None
) -> SkillSummary:
    """只返回元数据，供目录发现使用；正文不会进入返回值或模型上下文。"""
    meta, body = _split_frontmatter(text, origin=origin)
    slug, name, description, tools, icon = _metadata_fields(
        meta, origin=origin, default_slug=default_slug
    )
    if not body:
        raise SkillFormatError(f"{origin}: 正文不能为空")
    if len(body) > MAX_INSTRUCTIONS_CHARS:
        raise SkillFormatError(f"{origin}: 正文超过 {MAX_INSTRUCTIONS_CHARS} 字")
    return SkillSummary(
        slug=slug,
        name=name,
        description=description,
        tools=tools,
        icon=icon,
        source=SOURCE_BUILTIN,
    )


def parse_skill(text: str, *, origin: str = "SKILL.md", default_slug: str | None = None) -> Skill:
    """把一份 SKILL.md 解析成 `Skill`，顺手校验长度与 slug 规则。"""
    meta, body = _split_frontmatter(text, origin=origin)
    slug, name, description, tools, icon = _metadata_fields(
        meta, origin=origin, default_slug=default_slug
    )

    if not body:
        raise SkillFormatError(f"{origin}: 正文不能为空")
    if len(body) > MAX_INSTRUCTIONS_CHARS:
        raise SkillFormatError(f"{origin}: 正文超过 {MAX_INSTRUCTIONS_CHARS} 字")
    return Skill(slug, name, description, body, tools, icon, SOURCE_BUILTIN)


def load_builtin_skills(directory: Path | None = None) -> dict[str, Skill]:
    """扫描目录下的 `<slug>/SKILL.md`。目录不存在时返回空表（打包场景容错）。"""
    root = directory or SKILLS_DIR
    skills: dict[str, Skill] = {}
    if not root.is_dir():  # pragma: no cover - 正常安装不会缺目录
        return skills
    for path in sorted(root.glob(f"*/{SKILL_FILE}")):
        skill = parse_skill(
            path.read_text(encoding="utf-8"), origin=str(path), default_slug=path.parent.name
        )
        if skill.slug in skills:  # pragma: no cover - 目录名唯一，防手滑
            raise SkillFormatError(f"内置技能 slug 重复：{skill.slug}")
        skills[skill.slug] = skill
    return skills


def builtin_skill(slug: str) -> Skill | None:
    return load_builtin_skills().get(slug)
