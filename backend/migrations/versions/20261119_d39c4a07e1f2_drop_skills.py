"""drop_skills

下线旧版「数据库自定义 Skill」：技能只剩 `app/skills/<slug>/SKILL.md` 一种来源，
`skills` 表不再被任何代码读写（2026-11-19 时库内 0 行）。

Revision ID: d39c4a07e1f2
Revises: b0fc5a19fd76
Create Date: 2026-11-19 23:52:41.117302

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d39c4a07e1f2"
down_revision: str | Sequence[str] | None = "b0fc5a19fd76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_skills_user_id"), table_name="skills")
    op.drop_table("skills")


def downgrade() -> None:
    """Downgrade schema."""
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
