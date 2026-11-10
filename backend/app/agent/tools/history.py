"""历史检索工具：在**当前用户**的会话标题里找关键词。

这是「工具必须按用户隔离」的最小验证点：SQL 里强制带 `user_id`，
即使模型编出一个别人的会话 id 也读不到。
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools.base import ToolError, ToolLevel, spec_of
from app.models import Conversation

MAX_KEYWORD_LENGTH = 50


class SearchArgs(BaseModel):
    keyword: str = Field(
        min_length=1,
        max_length=MAX_KEYWORD_LENGTH,
        description="要在历史会话标题里查找的关键词",
    )
    limit: int = Field(default=5, ge=1, le=10, description="最多返回几条")


class SearchConversationsTool:
    name = "search_conversations"
    description = "在用户自己的历史会话标题里按关键词检索，返回最匹配的几条（只会看到自己的数据）。"
    args_model = SearchArgs
    level = ToolLevel.READ

    def __init__(self, session: Session) -> None:
        self._session = session

    def spec(self) -> dict[str, Any]:
        return spec_of(self)

    def run(self, args: BaseModel, *, user_id: int) -> str:
        assert isinstance(args, SearchArgs)
        keyword = args.keyword.strip()
        if not keyword:
            raise ToolError("关键词不能为空")

        statement = (
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.title.contains(keyword, autoescape=True),
            )
            .order_by(Conversation.update_time.desc())
            .limit(args.limit)
        )
        rows = self._session.scalars(statement).all()
        if not rows:
            return f"没有找到标题包含「{keyword}」的会话。"

        lines = [f"找到 {len(rows)} 个相关会话："]
        for index, row in enumerate(rows, start=1):
            moment = row.update_time.strftime("%Y-%m-%d %H:%M")
            lines.append(f"{index}. 「{row.title}」（最后更新 {moment}）")
        return "\n".join(lines)
