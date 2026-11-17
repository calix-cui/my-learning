"""保存账号级本地 Skill 目录快照。

Revision ID: a638c170ef92
Revises: 52f9b8c781ad
"""

import sqlalchemy as sa
from alembic import op

revision = "a638c170ef92"
down_revision = "52f9b8c781ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("skill_catalog", sa.JSON(), comment="当前账号已发现的本地 Skill 目录元数据快照"),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "skill_catalog")
