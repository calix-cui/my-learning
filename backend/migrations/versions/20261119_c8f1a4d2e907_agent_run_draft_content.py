"""记录正在生成的正文快照，供断线重连时先看到已有内容。

Revision ID: c8f1a4d2e907
Revises: b72e80d193ac
"""

import sqlalchemy as sa
from alembic import op

revision = "c8f1a4d2e907"
down_revision = "b72e80d193ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 两列都可空：旧运行没有快照，读到 None 与「还没开始生成」等价
    op.add_column(
        "agent_runs",
        sa.Column(
            "draft_content",
            sa.Text(),
            nullable=True,
            comment="当前轮已生成、尚未落成消息的正文快照",
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "draft_updated_time",
            sa.DateTime(),
            nullable=True,
            comment="正文快照的最后写入时间",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "draft_updated_time")
    op.drop_column("agent_runs", "draft_content")
