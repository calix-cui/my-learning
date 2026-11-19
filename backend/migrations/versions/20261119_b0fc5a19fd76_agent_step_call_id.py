"""agent_step_call_id

给工具步骤补上模型给的调用标识：同名工具接连调用时，结果靠它配对，
而不是「按名字找最近一条」。

Revision ID: b0fc5a19fd76
Revises: c8f1a4d2e907
Create Date: 2026-11-19 23:17:25.429136

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0fc5a19fd76"
down_revision: str | Sequence[str] | None = "c8f1a4d2e907"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "agent_steps",
        sa.Column(
            "call_id",
            sa.String(length=64),
            nullable=True,
            comment="模型给的调用标识，用来把结果对回自己的调用",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("agent_steps", "call_id")
