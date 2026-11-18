"""清理没有消息关联的已结束执行记录。

Revision ID: b72e80d193ac
Revises: a638c170ef92
"""

import sqlalchemy as sa
from alembic import op

revision = "b72e80d193ac"
down_revision = "a638c170ef92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    runs = sa.table(
        "agent_runs",
        sa.column("id", sa.Integer),
        sa.column("user_message_id", sa.Integer),
        sa.column("assistant_message_id", sa.Integer),
        sa.column("status", sa.String),
    )
    # 只清理没有任一消息锚点的终态运行，避免误删待审批或中断后的新运行。
    condition = sa.and_(
        runs.c.user_message_id.is_(None),
        runs.c.assistant_message_id.is_(None),
        runs.c.status.in_(("completed", "failed", "cancelled")),
    )
    obsolete_ids = sa.select(runs.c.id).where(condition)
    # 显式删除从表，兼容没有启用外键级联的测试数据库。
    for name in ("agent_steps", "agent_approvals"):
        table = sa.table(name, sa.column("run_id", sa.Integer))
        op.execute(table.delete().where(table.c.run_id.in_(obsolete_ids)))
    op.execute(runs.delete().where(condition))


def downgrade() -> None:
    # 数据清理不可逆，降级仅回退版本号，不伪造已删除的执行历史。
    pass
