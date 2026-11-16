"""persist skill mode and per-run skill snapshots

Revision ID: 8c1a4d7e2f90
Revises: 71c2a847d901
Create Date: 2026-11-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c1a4d7e2f90"
down_revision: str | Sequence[str] | None = "71c2a847d901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "skill_mode",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'manual'"),
            comment="off/manual/auto",
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("skill_snapshot", sa.JSON(), nullable=True, comment="本次运行的 Skill 快照"),
    )
    op.add_column(
        "agent_steps",
        sa.Column("skill_key", sa.String(length=128), nullable=True, comment="Skill 稳定标识"),
    )
    op.add_column(
        "agent_steps",
        sa.Column("skill_name", sa.String(length=128), nullable=True, comment="Skill 名称"),
    )
    op.add_column(
        "agent_steps",
        sa.Column("skill_source", sa.String(length=24), nullable=True, comment="Skill 来源"),
    )
    op.add_column(
        "agent_steps",
        sa.Column("skill_version", sa.String(length=64), nullable=True, comment="Skill 版本"),
    )


def downgrade() -> None:
    op.drop_column("agent_steps", "skill_version")
    op.drop_column("agent_steps", "skill_source")
    op.drop_column("agent_steps", "skill_name")
    op.drop_column("agent_steps", "skill_key")
    op.drop_column("agent_runs", "skill_snapshot")
    op.drop_column("agent_runs", "skill_mode")
