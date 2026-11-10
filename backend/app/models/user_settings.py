from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 只供类型检查工具使用，运行时不导入用户模块，避免互相导入。
if TYPE_CHECKING:
    from app.models.user import User

DEFAULT_TIMEOUT_SECONDS = 30
# 每个账号每日工具调用上限；阶段 6 先用默认值，够用再开放给用户改
DEFAULT_DAILY_TOOL_BUDGET = 500
DEFAULT_PROVIDER = "fake"


class UserSettings(Base):
    """用户级设置：一人一行（`user_id` 上有唯一索引）。

    分两块：模型接入（provider/base_url/model/超时/Key 密文）与外观（主题 id + 明暗模式）。
    外观为空时前端回落到 localStorage，所以老账号不受影响。
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
    # 是否真的保存过模型配置。外观（主题）也会在这一行落库，
    # 不能因为「有行」就认定用户配过模型，否则新账号会丢掉环境变量那套默认值。
    model_configured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否保存过模型配置"
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
    # 外观：为空表示「这个账号没存过」，前端用本机 localStorage 的值
    theme_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="主题 id（如 pine），未同步时为 NULL"
    )
    # 阶段 6：被用户关掉的工具名数组；空数组表示「全开」
    tools_disabled: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("('[]')"),
        comment="被关闭的工具名列表",
    )
    daily_tool_budget: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_DAILY_TOOL_BUDGET,
        server_default=text("500"),
        comment="每日工具调用上限",
    )
    theme_mode: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="明暗模式：light / dark / system"
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
