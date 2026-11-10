"""工具审批：写/外网级工具在真正执行前，需要用户点一下「允许」。

几个刻意的决定（对应 `docs/tools.md` §3.4）：

- **不设过期时间**：快模型慢用户是常态，超时判失败等于白跑一次运行；
- **状态在库里**：进程重启、多进程部署后仍能继续，不依赖内存里的事件对象；
- **一次运行只允许一条 pending**：避免一次弹五个确认框；
- 「被拒几次」不落成计数字段，直接数这张表里的 rejected 行，少一处需要保持一致的状态。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.user import User

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
APPROVAL_EXPIRED = "expired"

APPROVAL_STATUSES = (APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED, APPROVAL_EXPIRED)


class AgentApproval(Base):
    """一次「要不要允许调用某工具」的待决请求。"""

    __tablename__ = "agent_approvals"
    __table_args__ = {"comment": "Agent 工具审批表"}

    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属运行",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="决定人（run 的属主）",
    )
    seq: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="对应 agent_steps.seq，决定后写回同一条步骤线"
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="要调用的工具")
    tool_args: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="调用参数，给用户看清楚要做什么"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=APPROVAL_PENDING,
        comment="pending/approved/rejected/expired",
    )
    note: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="决定理由（用户可填）"
    )
    decided_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="决定时间"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )

    run: Mapped["AgentRun"] = relationship(back_populates="approvals")
    user: Mapped["User"] = relationship(back_populates="agent_approvals")


__all__ = [
    "APPROVAL_APPROVED",
    "APPROVAL_EXPIRED",
    "APPROVAL_PENDING",
    "APPROVAL_REJECTED",
    "APPROVAL_STATUSES",
    "AgentApproval",
]
