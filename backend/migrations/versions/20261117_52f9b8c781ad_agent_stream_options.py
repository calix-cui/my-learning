"""保存 Agent 的推理选项与审批续跑上下文。

Revision ID: 52f9b8c781ad
Revises: ae69f7e9c341
"""

import sqlalchemy as sa
from alembic import op

revision = "52f9b8c781ad"
down_revision = "ae69f7e9c341"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("request_id", sa.String(36), comment="同一会话内用于去重的客户端请求 ID"),
    )
    op.create_unique_constraint(
        "uq_agent_runs_request", "agent_runs", ["conversation_id", "request_id"]
    )
    op.add_column(
        "agent_runs",
        sa.Column("reasoning_effort", sa.String(8), comment="聊天推理强度；空值用于旧版接口"),
    )
    op.add_column(
        "agent_runs",
        sa.Column("approval_context", sa.JSON(), comment="等待审批时用于模型续跑的私有上下文"),
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_runs_request", "agent_runs", type_="unique")
    op.drop_column("agent_runs", "request_id")
    op.drop_column("agent_runs", "approval_context")
    op.drop_column("agent_runs", "reasoning_effort")
