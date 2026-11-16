"""align skill runtime and approval column comments

Revision ID: 9d3e5f7a1b20
Revises: 8c1a4d7e2f90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d3e5f7a1b20"
down_revision: str | Sequence[str] | None = "8c1a4d7e2f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "agent_approvals",
        "tool_fingerprint",
        existing_type=sa.String(64),
        existing_nullable=True,
        comment="审批时的工具定义摘要，恢复执行前复核",
    )
    op.alter_column(
        "agent_runs",
        "skill_snapshot",
        existing_type=sa.JSON(),
        existing_nullable=True,
        comment="本次运行发现的 Skill 元数据与已加载内容快照",
    )
    op.alter_column(
        "agent_steps",
        "kind",
        existing_type=sa.String(20),
        existing_nullable=False,
        comment="user_message/assistant_text/tool_call/tool_result/skill events/final_answer",
    )


def downgrade() -> None:
    op.alter_column(
        "agent_steps",
        "kind",
        existing_type=sa.String(20),
        existing_nullable=False,
        comment="user_message/assistant_text/tool_call/tool_result/final_answer",
    )
    op.alter_column(
        "agent_runs",
        "skill_snapshot",
        existing_type=sa.JSON(),
        existing_nullable=True,
        comment="本次运行的 Skill 快照",
    )
    op.alter_column(
        "agent_approvals",
        "tool_fingerprint",
        existing_type=sa.String(64),
        existing_nullable=True,
        comment=None,
    )
