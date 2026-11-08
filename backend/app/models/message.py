from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"comment": "对话消息表"}

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="角色：user/assistant/system"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息正文")
    # 用户消息没有模型，留空；助手消息记录生成它的模型，便于区分 fake 与真实模型。
    model: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="生成该回复的模型")

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
