"""add skills and conversations.skill_slug

Revision ID: a1b2c3d4e5f6
Revises: 4f9edca19113
Create Date: 2026-11-11 23:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "4f9edca19113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="所属用户"),
        sa.Column("slug", sa.String(length=32), nullable=False, comment="稳定标识，会话按它挂载"),
        sa.Column("name", sa.String(length=30), nullable=False, comment="展示名"),
        sa.Column(
            "description",
            sa.String(length=120),
            nullable=False,
            comment="一句话说明，展示在选择器里",
        ),
        sa.Column(
            "instructions",
            sa.Text(),
            nullable=False,
            comment="Markdown 正文，整体注入 system prompt",
        ),
        sa.Column(
            "tools",
            sa.JSON(),
            server_default=sa.text("('[]')"),
            nullable=False,
            comment="工具白名单，空数组表示不限制",
        ),
        sa.Column(
            "icon",
            sa.String(length=32),
            server_default="sparkle",
            nullable=False,
            comment="图标名",
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "slug", name="uq_skills_user_slug"),
        comment="用户自定义技能表",
    )
    op.create_index(op.f("ix_skills_user_id"), "skills", ["user_id"], unique=False)
    op.add_column(
        "conversations",
        sa.Column(
            "skill_slug",
            sa.String(length=32),
            nullable=True,
            comment="挂载的技能 slug；NULL 表示不挂",
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    先删列再删表：MySQL 的 DDL 不是事务，中途失败会留下半套 schema。
    索引随表一起删，单独 drop_index 会撞 1553（被外键依赖）。
    """
    op.drop_column("conversations", "skill_slug")
    op.drop_table("skills")
