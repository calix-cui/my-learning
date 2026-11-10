"""Agent 运行的一步：用户输入、模型文本、工具调用、工具结果、最终答复各一条。

`seq` 从 1 开始，同一 run 内递增；`(run_id, seq)` 唯一，保证顺序可重放。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun

# 步骤类型：前端时间线按它选图标与文案
STEP_USER_MESSAGE = "user_message"
STEP_ASSISTANT_TEXT = "assistant_text"
STEP_TOOL_CALL = "tool_call"
STEP_TOOL_RESULT = "tool_result"
STEP_FINAL_ANSWER = "final_answer"

STEP_KINDS = (
    STEP_USER_MESSAGE,
    STEP_ASSISTANT_TEXT,
    STEP_TOOL_CALL,
    STEP_TOOL_RESULT,
    STEP_FINAL_ANSWER,
)


class AgentStep(Base):
    """运行的单个步骤。"""

    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_steps_run_seq"),
        {"comment": "Agent 运行步骤表"},
    )

    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属运行",
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, comment="第几步，从 1 开始")
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="user_message/assistant_text/tool_call/tool_result/final_answer",
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="文本或工具结果摘要")
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="工具名")
    tool_args: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="已校验的工具参数"
    )
    ok: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="工具是否执行成功（仅 tool_result）"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="工具耗时毫秒")
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )

    run: Mapped["AgentRun"] = relationship(back_populates="steps")


__all__ = [
    "AgentStep",
    "STEP_ASSISTANT_TEXT",
    "STEP_FINAL_ANSWER",
    "STEP_KINDS",
    "STEP_TOOL_CALL",
    "STEP_TOOL_RESULT",
    "STEP_USER_MESSAGE",
]
