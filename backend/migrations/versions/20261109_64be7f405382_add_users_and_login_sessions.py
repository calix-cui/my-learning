"""add users and login sessions

Revision ID: 64be7f405382
Revises: 17fe0c7d2cb5
Create Date: 2026-11-09 15:14:29.689883

说明：conversations 需要新增非空的 user_id，直接加 NOT NULL 会在有数据时失败。
旧对话已确认不保留（见 ADR-0008），所以这里先加可空列、清空旧会话，再收紧为非空。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64be7f405382"
down_revision: str | Sequence[str] | None = "17fe0c7d2cb5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_CONVERSATIONS_USER = "fk_conversations_user_id_users"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("email", sa.String(length=255), nullable=False, comment="登录邮箱（统一小写）"),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            comment="密码哈希（Argon2id，含算法与参数）",
        ),
        sa.Column(
            "display_name",
            sa.String(length=50),
            nullable=True,
            comment="显示名，可为空，界面回落到邮箱",
        ),
        sa.Column("role", sa.String(length=20), nullable=False, comment="角色：user / admin"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否可登录（封禁开关）"),
        sa.Column("last_login_time", sa.DateTime(), nullable=True, comment="最近一次登录成功时间"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        comment="用户账号表",
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="所属用户"),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
            comment="登录令牌的 SHA-256 摘要（不存明文令牌）",
        ),
        sa.Column(
            "user_agent", sa.String(length=255), nullable=True, comment="登录设备信息，仅用于展示"
        ),
        sa.Column("ip", sa.String(length=64), nullable=True, comment="登录 IP，仅用于展示"),
        sa.Column(
            "last_seen_time", sa.DateTime(), nullable=False, comment="最近一次使用时间（滑动续期）"
        ),
        sa.Column("expires_time", sa.DateTime(), nullable=False, comment="过期时间"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        comment="登录会话表",
    )
    op.create_index(op.f("ix_sessions_expires_time"), "sessions", ["expires_time"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    # 先加可空列 → 清空旧对话（已确认不保留） → 再收紧为非空
    op.add_column(
        "conversations",
        sa.Column("user_id", sa.Integer(), nullable=True, comment="所属用户（数据隔离的唯一维度）"),
    )
    op.execute("DELETE FROM conversations")
    op.alter_column(
        "conversations",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
        existing_comment="所属用户（数据隔离的唯一维度）",
        comment="所属用户（数据隔离的唯一维度）",
    )
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_foreign_key(
        FK_CONVERSATIONS_USER,
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FK_CONVERSATIONS_USER, "conversations", type_="foreignkey")
    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_column("conversations", "user_id")
    # 直接删表即可：sessions 上的索引与外键随表一起消失，
    # 单独 DROP INDEX 会因为该索引正被外键使用而报 1553/1091。
    op.drop_table("sessions")
    op.drop_table("users")
