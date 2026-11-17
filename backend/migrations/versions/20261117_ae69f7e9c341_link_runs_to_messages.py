"""关联 Agent 运行与用户消息、最终助手消息。

Revision ID: ae69f7e9c341
Revises: 9d3e5f7a1b20
"""

import sqlalchemy as sa
from alembic import op

revision = "ae69f7e9c341"
down_revision = "9d3e5f7a1b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch:
        for column, comment in (
            ("user_message_id", "触发运行的用户消息"),
            ("assistant_message_id", "运行生成的最终助手消息"),
        ):
            batch.add_column(sa.Column(column, sa.Integer(), nullable=True, comment=comment))
            batch.create_index(
                f"ix_agent_runs_{column}", [column], unique=column == "assistant_message_id"
            )
            batch.create_foreign_key(
                f"fk_agent_runs_{column.removesuffix('_id')}",
                "messages",
                [column],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch:
        for column in ("assistant_message_id", "user_message_id"):
            batch.drop_constraint(f"fk_agent_runs_{column.removesuffix('_id')}", type_="foreignkey")
            batch.drop_index(f"ix_agent_runs_{column}")
            batch.drop_column(column)
