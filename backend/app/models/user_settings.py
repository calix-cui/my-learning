from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 只供类型检查工具使用，运行时不导入用户模块，避免互相导入。
if TYPE_CHECKING:
    from app.models.user import User

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_PROVIDER = "fake"


class UserSettings(Base):
    """用户级设置：一人一行（`user_id` 上有唯一索引）。

    目前只放模型接入；外观之类的纯前端偏好继续留在 localStorage，
    等需要跨设备同步时再加列。
    """

    __tablename__ = "user_settings"
    __table_args__ = {"comment": "用户设置表"}

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="所属用户（一对一）",
    )
    model_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DEFAULT_PROVIDER, comment="模型来源：fake / openai"
    )
    model_base_url: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="OpenAI 兼容服务的 base URL"
    )
    model_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="模型名")
    model_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_TIMEOUT_SECONDS, comment="单次请求超时（秒）"
    )
    # Key 只存密文 + 末四位提示；任何接口都不返回明文
    model_api_key_ciphertext: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="API Key 密文（Fernet），未配置时为 NULL"
    )
    model_api_key_hint: Mapped[str | None] = mapped_column(
        String(8), nullable=True, comment="API Key 末四位，用于界面回显"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="最后修改时间",
    )

    user: Mapped["User"] = relationship(back_populates="settings")
