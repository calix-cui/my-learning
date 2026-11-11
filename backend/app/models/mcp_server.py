"""用户接入的 MCP 服务器。

一个用户可以为每个 server slug 接入一次（`UniqueConstraint(user_id, slug)`）。
表里存的是**接入参数**与**最近一次连接结果**，不存工具清单——工具是连接时发现的，
缓存会过期，存库反而制造不一致。

敏感信息只有 `env`（常放 token），复用阶段 4 的 Fernet 加密成 `env_ciphertext`，
接口永远只回「配置了哪些键」，不回值。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User

STATUS_UNKNOWN = "unknown"
STATUS_OK = "ok"
STATUS_ERROR = "error"

SERVER_STATUSES = (STATUS_UNKNOWN, STATUS_OK, STATUS_ERROR)


class McpServer(Base):
    """一个已接入的 MCP 服务器。"""

    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_mcp_servers_user_slug"),
        {"comment": "MCP 服务器接入表"},
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="属主",
    )
    slug: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="标识，会进工具名 mcp__{slug}__{tool}"
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="展示名")
    transport: Mapped[str] = mapped_column(String(8), nullable=False, comment="stdio / http")
    command: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="stdio 启动命令（受白名单约束）"
    )
    args: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="stdio 启动参数")
    url: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="http 端点（必须 https）"
    )
    env_ciphertext: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="环境变量 JSON 的 Fernet 密文"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="关闭后模型看不到它的工具"
    )
    last_status: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default=STATUS_UNKNOWN,
        comment="unknown/ok/error：最近一次连接结果",
    )
    last_error: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="最近一次失败原因（给人看）"
    )
    tool_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="最近一次成功连接时列出的工具数"
    )
    last_connected_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次成功连接时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )

    user: Mapped["User"] = relationship(back_populates="mcp_servers")

    @property
    def spec_payload(self) -> dict[str, Any]:
        """给 `McpServerSpec` 用的原始参数（不含解密后的 env）。"""
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "transport": self.transport,
            "command": self.command,
            "args": tuple(self.args or ()),
            "url": self.url,
        }


__all__ = [
    "SERVER_STATUSES",
    "STATUS_ERROR",
    "STATUS_OK",
    "STATUS_UNKNOWN",
    "McpServer",
]
