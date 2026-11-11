"""技能的读写与挂载。

内置技能来自 `app/skills/`（只读），自定义技能存 `skills` 表。
接口层只拿 `Skill`（统一形状），不关心来源。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.models import Conversation
from app.models import Skill as SkillRow
from app.skills import BUILTIN_SKILLS, MAX_INSTRUCTIONS_CHARS, Skill, build_system_prompt
from app.skills.models import (
    MAX_DESCRIPTION_CHARS,
    MAX_NAME_CHARS,
    MAX_TOOLS,
    SKILL_SLUG_PATTERN,
    SOURCE_CUSTOM,
)


def _row_to_skill(row: SkillRow) -> Skill:
    return Skill(
        slug=row.slug,
        name=row.name,
        description=row.description,
        instructions=row.instructions,
        tools=tuple(row.tools or ()),
        icon=row.icon,
        source=SOURCE_CUSTOM,
        skill_id=row.id,
    )


def list_skills(db: Session, user_id: int) -> list[Skill]:
    """内置 + 自定义。同名时内置优先（建的时候已挡住重名，这里只是兜底）。"""
    rows = db.scalars(select(SkillRow).where(SkillRow.user_id == user_id).order_by(SkillRow.id))
    custom = [_row_to_skill(row) for row in rows]
    taken = set(BUILTIN_SKILLS)
    return list(BUILTIN_SKILLS.values()) + [item for item in custom if item.slug not in taken]


def get_skill(db: Session, user_id: int, slug: str) -> Skill | None:
    builtin = BUILTIN_SKILLS.get(slug)
    if builtin is not None:
        return builtin
    row = db.scalar(select(SkillRow).where(SkillRow.user_id == user_id, SkillRow.slug == slug))
    return _row_to_skill(row) if row is not None else None


def _validate(
    *,
    slug: str,
    name: str,
    description: str,
    instructions: str,
    tools: list[str],
) -> None:
    if not SKILL_SLUG_PATTERN.match(slug):
        raise BusinessError("标识只能用小写字母、数字和连字符，且不超过 32 个字符")
    if not name.strip() or len(name.strip()) > MAX_NAME_CHARS:
        raise BusinessError(f"名称必填，且不超过 {MAX_NAME_CHARS} 字")
    if not description.strip() or len(description.strip()) > MAX_DESCRIPTION_CHARS:
        raise BusinessError(f"说明必填，且不超过 {MAX_DESCRIPTION_CHARS} 字")
    if not instructions.strip():
        raise BusinessError("说明正文不能为空")
    if len(instructions) > MAX_INSTRUCTIONS_CHARS:
        raise BusinessError(f"说明正文不能超过 {MAX_INSTRUCTIONS_CHARS} 字")
    if len(tools) > MAX_TOOLS:
        raise BusinessError(f"工具白名单最多 {MAX_TOOLS} 个")


def create_skill(
    db: Session,
    user_id: int,
    *,
    slug: str,
    name: str,
    description: str,
    instructions: str,
    tools: list[str],
    icon: str = "sparkle",
) -> Skill:
    slug = slug.strip().lower()
    _validate(
        slug=slug,
        name=name,
        description=description,
        instructions=instructions,
        tools=tools,
    )
    if slug in BUILTIN_SKILLS:
        raise BusinessError("这个标识被内置技能占用了，换一个")
    exists = db.scalar(
        select(SkillRow.id).where(SkillRow.user_id == user_id, SkillRow.slug == slug)
    )
    if exists is not None:
        raise BusinessError("已经有同标识的技能了")

    row = SkillRow(
        user_id=user_id,
        slug=slug,
        name=name.strip(),
        description=description.strip(),
        instructions=instructions.strip(),
        tools=[item for item in tools if item],
        icon=icon or "sparkle",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_skill(row)


def _own_row(db: Session, user_id: int, skill_id: int) -> SkillRow:
    row = db.scalar(select(SkillRow).where(SkillRow.id == skill_id, SkillRow.user_id == user_id))
    if row is None:
        # 内置技能只读，也不该出现在「编辑」路径里：统一 404，不暴露存在性
        raise BusinessError("技能不存在", code=404)
    return row


def update_skill(
    db: Session,
    user_id: int,
    skill_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    instructions: str | None = None,
    tools: list[str] | None = None,
    icon: str | None = None,
) -> Skill:
    row = _own_row(db, user_id, skill_id)
    _validate(
        slug=row.slug,
        name=name if name is not None else row.name,
        description=description if description is not None else row.description,
        instructions=instructions if instructions is not None else row.instructions,
        tools=tools if tools is not None else list(row.tools or ()),
    )
    if name is not None:
        row.name = name.strip()
    if description is not None:
        row.description = description.strip()
    if instructions is not None:
        row.instructions = instructions.strip()
    if tools is not None:
        row.tools = [item for item in tools if item]
    if icon is not None:
        row.icon = icon or "sparkle"
    db.commit()
    db.refresh(row)
    return _row_to_skill(row)


def delete_skill(db: Session, user_id: int, skill_id: int) -> None:
    row = _own_row(db, user_id, skill_id)
    # 挂了这个技能还把它删掉：会话回落到「不挂技能」，不做级联删除
    db.execute(
        Conversation.__table__.update()
        .where(Conversation.user_id == user_id, Conversation.skill_slug == row.slug)
        .values(skill_slug=None)
    )
    db.delete(row)
    db.commit()


def mount_skill(db: Session, user_id: int, conversation_id: int, slug: str | None) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conversation is None:
        raise BusinessError("会话不存在", code=404)
    if slug is not None:
        if get_skill(db, user_id, slug) is None:
            raise BusinessError("技能不存在", code=404)
        conversation.skill_slug = slug
    else:
        conversation.skill_slug = None
    db.commit()
    db.refresh(conversation)
    return conversation


def mounted_skill(db: Session, user_id: int, conversation: Conversation) -> Skill | None:
    """会话当前挂载的技能；挂了但已被删掉时返回 None（不报错）。"""
    if not conversation.skill_slug:
        return None
    return get_skill(db, user_id, conversation.skill_slug)


def system_prompt_for(
    db: Session, user_id: int, conversation: Conversation, *, tool_names: list[str]
) -> str | None:
    skill = mounted_skill(db, user_id, conversation)
    if skill is None:
        return None
    return build_system_prompt(skill, tool_names=tool_names)
