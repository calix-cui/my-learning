"""add appearance settings

Revision ID: bf5564d3b5b6
Revises: 7ccc172700f4
Create Date: 2026-11-10 15:10:21.343439

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bf5564d3b5b6"
down_revision: str | Sequence[str] | None = "7ccc172700f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 两列都可空：老账号没存过，前端回落到 localStorage
    op.add_column(
        "user_settings",
        sa.Column(
            "theme_id",
            sa.String(length=32),
            nullable=True,
            comment="主题 id（如 pine），未同步时为 NULL",
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "theme_mode",
            sa.String(length=10),
            nullable=True,
            comment="明暗模式：light / dark / system",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_settings", "theme_mode")
    op.drop_column("user_settings", "theme_id")
