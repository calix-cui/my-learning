from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 只供类型检查工具使用，运行时不导入用户模块，避免互相导入。
if TYPE_CHECKING:
    from app.models.user import User


class LoginSession(Base):
    """一次登录对应一行；删掉这行就等于让该设备立即下线。"""

    __tablename__ = "sessions"
    __table_args__ = {"comment": "登录会话表"}

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户",
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="登录令牌的 SHA-256 摘要（不存明文令牌）",
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="登录设备信息，仅用于展示"
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="登录 IP，仅用于展示")
    last_seen_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="最近一次使用时间（滑动续期）"
    )
    expires_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, comment="过期时间"
    )
    user: Mapped["User"] = relationship(back_populates="sessions")
