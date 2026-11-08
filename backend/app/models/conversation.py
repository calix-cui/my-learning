from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 只供类型检查工具使用，运行时不导入消息模块，避免互相导入。
if TYPE_CHECKING:
    from app.models.message import Message


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"comment": "对话会话表"}

    title: Mapped[str] = mapped_column(
        String(100), nullable=False, default="新会话", comment="会话标题"
    )
    agent_key: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default", comment="所属代理标识（预留多代理）"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        index=True,
        comment="最后活动时间（列表按它倒序）",
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )
