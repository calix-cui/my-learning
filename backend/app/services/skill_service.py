"""技能的读取与挂载。

技能只有一种来源：`app/skills/<slug>/SKILL.md` 里的只读文件，
由 `FileSystemSkillProvider` 按账号作用域读取。接口层只拿 `Skill`，不关心文件在哪。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.dev_trace import trace
from app.common.exceptions import BusinessError
from app.models import Conversation
from app.skills import FileSystemSkillProvider, Skill, SkillRegistry, build_system_prompt


def registry_for(db: Session, user_id: int) -> SkillRegistry:
    """返回本次请求的技能目录，供 Agent Runtime 发现和按需加载。

    现在只有文件来源，参数保留是为了调用方（执行器、接口）不必关心目录怎么拼；
    以后加数据库来源时在这里接。
    """
    del db, user_id
    return SkillRegistry([FileSystemSkillProvider()])


def describe_skill(db: Session, user_id: int, slug: str):
    """只取 Skill 元数据，避免为了权限收窄而提前读取正文。"""
    return next((item for item in registry_for(db, user_id).discover() if item.slug == slug), None)


def mount_skill(db: Session, user_id: int, conversation_id: int, slug: str | None) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conversation is None:
        raise BusinessError("会话不存在", code=404)
    if slug is not None:
        if not registry_for(db, user_id).contains_slug(slug):
            raise BusinessError("技能不存在", code=404)
        conversation.skill_slug = slug
    else:
        conversation.skill_slug = None
    db.commit()
    db.refresh(conversation)
    trace(
        "skill.settings.mount", conversation_id=conversation_id, slug=slug, mounted=slug is not None
    )
    return conversation


def mounted_skill(db: Session, user_id: int, conversation: Conversation) -> Skill | None:
    """会话当前挂载的技能；挂了但已被删掉时返回 None（不报错）。"""
    if not conversation.skill_slug:
        return None
    return describe_skill(db, user_id, conversation.skill_slug)  # type: ignore[return-value]


def system_prompt_for(
    db: Session, user_id: int, conversation: Conversation, *, tool_names: list[str]
) -> str | None:
    skill = mounted_skill(db, user_id, conversation)
    if skill is None:
        return None
    return build_system_prompt(skill, tool_names=tool_names)
