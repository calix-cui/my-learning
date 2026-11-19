from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 只供类型检查工具使用，运行时不导入其他模型模块，避免互相导入。
if TYPE_CHECKING:
    from app.models.agent_approval import AgentApproval
    from app.models.agent_run import AgentRun
    from app.models.conversation import Conversation
    from app.models.mcp_server import McpServer
    from app.models.session import LoginSession
    from app.models.user_settings import UserSettings


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户账号表"}

    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="登录邮箱（统一小写）"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希（Argon2id，含算法与参数）"
    )
    display_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="显示名，可为空，界面回落到邮箱"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", comment="角色：user / admin"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否可登录（封禁开关）"
    )
    last_login_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次登录成功时间"
    )
    settings: Mapped["UserSettings | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    sessions: Mapped[list["LoginSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # 注销账号时要连带删掉对话：没有 delete-orphan 的 relationship 会让
    # SQLAlchemy 先把 user_id 置空（NOT NULL 列 → 1048 报错），而不是删行。
    agent_approvals: Mapped[list["AgentApproval"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    mcp_servers: Mapped[list["McpServer"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )
