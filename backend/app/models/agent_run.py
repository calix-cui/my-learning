"""Agent 运行记录：一次「提问 → 循环 → 收尾」算一条。

和 `messages` 的分工：
- `messages` 是**用户看到的内容**（一问一答）；
- `agent_runs` / `agent_steps` 是**运行过程**（中间调了哪些工具、每步多久）。

只把最终答复写回 `messages`，中间步骤留在这里，供前端时间线与问题排查使用。
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.agent_approval import AgentApproval
    from app.models.agent_step import AgentStep
    from app.models.conversation import Conversation
    from app.models.user import User

# 运行状态：running 是进行中，其余都是终态
RUN_RUNNING = "running"
# 等用户确认某次工具调用；状态持久化在库里，进程重启也能继续
RUN_WAITING_APPROVAL = "waiting_approval"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"


class AgentRun(Base):
    """一次 agent 运行。"""

    __tablename__ = "agent_runs"
    __table_args__ = {"comment": "Agent 运行记录表"}

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话",
    )
    # 冗余一份 user_id：注销用户时可以直接按它级联清理，也便于统计
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户（数据隔离维度）",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RUN_RUNNING,
        comment="running/waiting_approval/completed/failed/cancelled",
    )
    step_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="已执行的步骤数"
    )
    model: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="实际使用的模型名")
    started_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="开始时间"
    )
    finished_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="结束时间"
    )
    error_message: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="失败原因（可展示给用户）"
    )

    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentStep.seq",
    )
    approvals: Mapped[list["AgentApproval"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentApproval.id",
    )
    conversation: Mapped["Conversation"] = relationship(back_populates="agent_runs")
    user: Mapped["User"] = relationship(back_populates="agent_runs")


__all__ = [
    "AgentRun",
    "RUN_CANCELLED",
    "RUN_COMPLETED",
    "RUN_FAILED",
    "RUN_RUNNING",
    "RUN_WAITING_APPROVAL",
]
