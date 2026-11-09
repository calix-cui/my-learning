import logging
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.llm import ChatMessage, LLMClient, LLMError
from app.models import Conversation, Message
from app.schemas.chat import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationUpdateRequest,
)

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "新会话"
# 上下文窗口：最近 20 条，超出直接截断（摘要留给阶段 8 的 Memory）
CONTEXT_LIMIT = 20
TITLE_MAX_LENGTH = 30


def create_conversation(
    db: Session, user_id: int, payload: ConversationCreateRequest
) -> Conversation:
    title = (payload.title or "").strip() or DEFAULT_TITLE
    conversation = Conversation(user_id=user_id, title=title)
    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("新建会话失败")
        raise
    return conversation


def list_conversations(db: Session, user_id: int, page: int = 1, page_size: int = 10) -> dict:
    try:
        total = (
            db.scalar(select(func.count(Conversation.id)).where(Conversation.user_id == user_id))
            or 0
        )
        rows = db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
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


def get_conversation(db: Session, user_id: int, conversation_id: int) -> Conversation:
    """按「当前用户 + 会话 id」取会话：别人的会话在这里和不存在是一个结果（404）。"""
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conversation is None:
        raise BusinessError("会话不存在", code=404)
    return conversation


def rename_conversation(
    db: Session, user_id: int, conversation_id: int, payload: ConversationUpdateRequest
) -> Conversation:
    # 先判存在，保证「id 不存在 + 空标题」返回 404 而不是 400
    conversation = get_conversation(db, user_id, conversation_id)
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


def delete_conversation(db: Session, user_id: int, conversation_id: int) -> None:
    conversation = get_conversation(db, user_id, conversation_id)
    try:
        db.delete(conversation)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("删除会话失败")
        raise


def _build_context(db: Session, conversation_id: int) -> list[ChatMessage]:
    """拼上下文：system 消息始终带上，其余取最近 CONTEXT_LIMIT 条，按时间正序。"""
    system_rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role == "system")
        .order_by(Message.id)
    ).all()
    recent_rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role != "system")
        .order_by(Message.id.desc())
        .limit(CONTEXT_LIMIT)
    ).all()
    ordered = [*system_rows, *reversed(recent_rows)]
    return [ChatMessage(role=row.role, content=row.content) for row in ordered]


def send_message(
    db: Session, user_id: int, conversation_id: int, content: str, llm: LLMClient
) -> tuple[Message, Message]:
    """写入用户消息、调用模型、写入回复。

    两条消息在同一个事务里提交：模型失败时整体回滚，库里不留半条对话，
    用户重试不会看到「自己的消息在、回复没有」的中间态。
    """
    conversation = get_conversation(db, user_id, conversation_id)
    text = content.strip()
    if not text:
        raise BusinessError("消息内容不能只包含空白")

    try:
        is_first_message = (
            db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
            )
            == 0
        )
        user_message = Message(conversation_id=conversation_id, role="user", content=text)
        db.add(user_message)
        # flush 而不是 commit：先拿到 id，让本次提问进入上下文，同时保持一个事务
        db.flush()

        reply = llm.chat(_build_context(db, conversation_id))

        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply["content"],
            model=reply["model"],
        )
        db.add(assistant_message)

        # 首轮对话自动命名：标题仍是默认值且这是第一条消息
        if is_first_message and conversation.title == DEFAULT_TITLE:
            conversation.title = text[:TITLE_MAX_LENGTH]
        # onupdate 只在会话行真正被 UPDATE 时触发，这里显式改时间，保证列表排序正确。
        # 全项目时间列都是 naive datetime（见 models 的 create_time），这里保持一致
        conversation.update_time = datetime.now()  # noqa: DTZ005

        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
    except BusinessError:
        # 含 LLMError / LLMTimeoutError：回滚掉未提交的两条消息，把 502/504 原样抛给上层
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.exception("发送消息失败")
        raise

    return user_message, assistant_message


def prepare_stream(
    db: Session, user_id: int, conversation_id: int, content: str
) -> tuple[Conversation, Message, list[ChatMessage], bool]:
    """流式回复的前置步骤：校验 + 落用户消息 + 拼上下文。

    放在生成器外面，是为了让 404/400 还能返回普通 JSON；一旦开始流式输出，
    状态码就固定了，错误只能走 SSE 的 error 事件。
    """
    conversation = get_conversation(db, user_id, conversation_id)
    text = content.strip()
    if not text:
        raise BusinessError("消息内容不能只包含空白")

    try:
        is_first_message = (
            db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
            )
            == 0
        )
        user_message = Message(conversation_id=conversation_id, role="user", content=text)
        db.add(user_message)
        db.flush()
        # 上下文先在内存里拼好，流式过程中不再查库，也不依赖 session 的迭代状态
        context = _build_context(db, conversation_id)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("准备流式回复失败")
        raise
    return conversation, user_message, context, is_first_message


def stream_reply(
    db: Session,
    conversation: Conversation,
    user_message: Message,
    context: list[ChatMessage],
    is_first_message: bool,
    llm: LLMClient,
) -> Iterator[dict]:
    """逐块产出 SSE 事件；流正常结束才落 assistant 消息，中途断开或出错整体回滚。

    事件类型：meta（带回 user_message）/ delta（增量文本）/ done（最终消息）/ error。
    """
    from app.schemas.chat import MessageResponse

    committed = False
    try:
        yield {
            "type": "meta",
            "user_message": MessageResponse.model_validate(user_message).model_dump(),
        }

        pieces: list[str] = []
        for piece in llm.stream(context):
            pieces.append(piece)
            yield {"type": "delta", "content": piece}

        reply_text = "".join(pieces).strip()
        if not reply_text:
            raise LLMError("模型返回内容为空")

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=reply_text,
            model=getattr(llm, "model", None),
        )
        db.add(assistant_message)

        if is_first_message and conversation.title == DEFAULT_TITLE:
            conversation.title = user_message.content[:TITLE_MAX_LENGTH]
        conversation.update_time = datetime.now()  # noqa: DTZ005

        db.commit()
        committed = True
        db.refresh(assistant_message)

        yield {
            "type": "done",
            "conversation_id": conversation.id,
            "conversation_title": conversation.title,
            "message_count": db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation.id)
            )
            or 0,
            "assistant_message": MessageResponse.model_validate(assistant_message).model_dump(),
        }
    except BusinessError as exc:
        db.rollback()
        yield {"type": "error", "code": exc.code, "message": str(exc)}
    except Exception:
        db.rollback()
        logger.exception("流式回复失败")
        yield {"type": "error", "code": 500, "message": "回复生成失败，请稍后重试"}
    finally:
        # 客户端提前断开（GeneratorExit）时也要保证半截数据不落库
        if not committed:
            db.rollback()
