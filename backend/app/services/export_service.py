"""数据导出：把当前用户的全部会话与消息序列化成 JSON 或 Markdown 流。

为什么用流式：会话数量与内容长度都由用户决定，一次性拼成字符串再返回，
内存与响应时间都会随数据量线性涨；这里按会话逐段 yield，前端边收边存。
"""

import json
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message, User

FORMATS = ("json", "markdown")


def _iter_messages(db: Session, conversation_id: int) -> Iterator[Message]:
    yield from db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    )


def _format_time(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def export_json(db: Session, user: User) -> Iterator[str]:
    """逐会话 yield，避免把整个账号的数据一次性放进内存。"""
    head = {
        "exported_at": _format_time(datetime.now()),  # noqa: DTZ005 与本项目其他表一致，存本地时间
        "schema": "my-agent.export.v1",
        "user": {"email": user.email, "display_name": user.display_name},
    }
    yield json.dumps(head, ensure_ascii=False)[:-1] + ', "conversations": ['

    conversations = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id)
    ).all()

    for index, conversation in enumerate(conversations):
        item = {
            "id": conversation.id,
            "title": conversation.title,
            "agent_key": conversation.agent_key,
            "create_time": _format_time(conversation.create_time),
            "update_time": _format_time(conversation.update_time),
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "model": message.model,
                    "create_time": _format_time(message.create_time),
                }
                for message in _iter_messages(db, conversation.id)
            ],
        }
        prefix = ", " if index else ""
        yield prefix + json.dumps(item, ensure_ascii=False)

    yield "]}\n"


def export_markdown(db: Session, user: User) -> Iterator[str]:
    """人读格式：每个会话一节，消息按时间顺序，助手消息标注模型。"""
    conversations = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id)
    ).all()

    yield "# My Agent 对话导出\n\n"
    yield f"- 账号：{user.email}\n"
    yield f"- 导出时间：{_format_time(datetime.now())}\n"  # noqa: DTZ005
    yield f"- 会话数：{len(conversations)}\n\n---\n\n"

    for conversation in conversations:
        yield f"## {conversation.title}\n\n"
        yield f"创建 {_format_time(conversation.create_time)} · 更新 {_format_time(conversation.update_time)}\n\n"
        for message in _iter_messages(db, conversation.id):
            who = "我" if message.role == "user" else "助手"
            model = f"（{message.model}）" if message.model else ""
            yield f"**{who}{model}** · {_format_time(message.create_time)}\n\n"
            yield f"{message.content}\n\n"
        yield "---\n\n"
