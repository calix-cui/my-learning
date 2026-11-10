"""会话改名工具：阶段 6 的第一个**写工具**，用来把审批链路跑通。

写操作一律走审批（`ToolLevel.WRITE`）：模型只能「申请改名」，
用户点了批准才真的落库。SQL 里强制带 `user_id`，改不到别人的会话。
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolError, ToolLevel, spec_of
from app.models import Conversation

MAX_TITLE_LENGTH = 30


class RenameArgs(BaseModel):
    conversation_id: int = Field(ge=1, description="要改名的会话ID（必须是自己的会话）")
    title: str = Field(
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
        description="新的会话标题",
    )


class RenameConversationTool:
    name = "rename_conversation"
    description = "把一个会话改名。属于写操作，需要用户确认后才会真正执行。"
    args_model = RenameArgs
    level = ToolLevel.WRITE

    def __init__(self, session: Session) -> None:
        self._session = session

    def spec(self) -> dict[str, Any]:
        return spec_of(self)

    def run(self, args: BaseModel, *, user_id: int) -> str:
        assert isinstance(args, RenameArgs)
        title = args.title.strip()
        if not title:
            raise ToolError("标题不能为空")

        conversation = self._session.scalar(
            select(Conversation).where(
                Conversation.id == args.conversation_id,
                Conversation.user_id == user_id,
            )
        )
        if conversation is None:
            raise ToolError("没有找到这个会话")

        old_title = conversation.title
        conversation.title = title
        self._session.commit()
        return f"已把会话「{old_title}」改名为「{title}」。"
