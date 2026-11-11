from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Skill(Base):
    """用户自定义技能。内置技能在 `app/skills/<slug>/SKILL.md`，不进这张表。"""

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_skills_user_slug"),
        {"comment": "用户自定义技能表"},
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户",
    )
    slug: Mapped[str] = mapped_column(String(32), nullable=False, comment="稳定标识，会话按它挂载")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="展示名")
    description: Mapped[str] = mapped_column(
        String(120), nullable=False, comment="一句话说明，展示在选择器里"
    )
    instructions: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Markdown 正文，整体注入 system prompt"
    )
    tools: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("('[]')"),
        comment="工具白名单，空数组表示不限制",
    )
    icon: Mapped[str] = mapped_column(
        String(32), nullable=False, default="sparkle", server_default="sparkle", comment="图标名"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )

    user: Mapped["User"] = relationship(back_populates="skills")
