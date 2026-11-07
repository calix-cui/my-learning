import logging

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.models import Conversation, Message
from app.schemas.chat import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationUpdateRequest,
)

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "新会话"


def create_conversation(db: Session, payload: ConversationCreateRequest) -> Conversation:
    title = (payload.title or "").strip() or DEFAULT_TITLE
    conversation = Conversation(title=title)
    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("新建会话失败")
        raise
    return conversation


def list_conversations(db: Session, page: int = 1, page_size: int = 10) -> dict:
    try:
        total = db.scalar(select(func.count(Conversation.id))) or 0
        rows = db.scalars(
            select(Conversation)
            # 最近聊过的排前面；同一秒创建时用 id 倒序保证顺序稳定
            .order_by(Conversation.update_time.desc(), Conversation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        counts: dict[int, int] = {}
        if rows:
            count_rows = db.execute(
                select(Message.conversation_id, func.count(Message.id))
                .where(Message.conversation_id.in_([c.id for c in rows]))
                .group_by(Message.conversation_id)
            ).all()
            counts = dict(count_rows)

        items = [
            {
                **ConversationResponse.model_validate(conversation).model_dump(),
                "message_count": counts.get(conversation.id, 0),
            }
            for conversation in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    except SQLAlchemyError as exc:
        logger.exception("查询会话列表失败")
        raise BusinessError("查询会话列表失败，请稍后重试", code=500) from exc


def get_conversation(db: Session, conversation_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise BusinessError("会话不存在", code=404)
    return conversation


def rename_conversation(
    db: Session, conversation_id: int, payload: ConversationUpdateRequest
) -> Conversation:
    # 先判存在，保证「id 不存在 + 空标题」返回 404 而不是 400
    conversation = get_conversation(db, conversation_id)
    title = payload.title.strip()
    if not title:
        raise BusinessError("会话标题不能只包含空白")
    try:
        conversation.title = title
        db.commit()
        db.refresh(conversation)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("重命名会话失败")
        raise
    return conversation


def delete_conversation(db: Session, conversation_id: int) -> None:
    conversation = get_conversation(db, conversation_id)
    try:
        db.delete(conversation)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("删除会话失败")
        raise
