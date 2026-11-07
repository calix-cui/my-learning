"""会话服务层测试：内存 SQLite，覆盖增删改查、分页排序与级联删除。"""

import pytest

from app.common.exceptions import BusinessError
from app.models import Conversation, Message
from app.schemas.chat import ConversationCreateRequest, ConversationUpdateRequest
from app.services import chat_service


def _add_message(db, conversation: Conversation, role: str, content: str) -> Message:
    message = Message(conversation_id=conversation.id, role=role, content=content)
    db.add(message)
    db.commit()
    return message


def test_create_conversation_uses_default_title(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())

    assert conversation.title == "新会话"
    assert conversation.agent_key == "default"
    assert conversation.id > 0
    assert conversation.update_time is not None


def test_create_conversation_trims_title(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="  商品定价  ")
    )

    assert conversation.title == "商品定价"


def test_create_conversation_blank_title_falls_back_to_default(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="   ")
    )

    assert conversation.title == "新会话"


def test_list_conversations_orders_by_update_time_desc(db_session):
    first = chat_service.create_conversation(db_session, ConversationCreateRequest(title="早"))
    second = chat_service.create_conversation(db_session, ConversationCreateRequest(title="晚"))
    _add_message(db_session, first, "user", "让 first 变成最近活动")
    # update_time 有 onupdate，写入消息不会自动改会话，这里手动触发一次更新
    first.title = "早（已更新）"
    db_session.commit()

    page = chat_service.list_conversations(db_session)

    assert page["total"] == 2
    assert [item["title"] for item in page["items"]] == ["早（已更新）", "晚"]
    assert second.id != first.id


def test_list_conversations_counts_messages(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="有消息")
    )
    _add_message(db_session, conversation, "user", "你好")
    _add_message(db_session, conversation, "assistant", "在的")
    chat_service.create_conversation(db_session, ConversationCreateRequest(title="空会话"))

    page = chat_service.list_conversations(db_session)

    counts = {item["title"]: item["message_count"] for item in page["items"]}
    assert counts == {"有消息": 2, "空会话": 0}


def test_list_conversations_paginates(db_session):
    for index in range(3):
        chat_service.create_conversation(
            db_session, ConversationCreateRequest(title=f"会话{index}")
        )

    page = chat_service.list_conversations(db_session, page=2, page_size=2)

    assert page["total"] == 3
    assert len(page["items"]) == 1
    assert page["page"] == 2
    assert page["page_size"] == 2


def test_get_conversation_returns_messages_in_order(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="顺序")
    )
    _add_message(db_session, conversation, "user", "第一句")
    _add_message(db_session, conversation, "assistant", "第二句")

    loaded = chat_service.get_conversation(db_session, conversation.id)

    assert [m.content for m in loaded.messages] == ["第一句", "第二句"]


def test_get_conversation_missing_raises_404(db_session):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.get_conversation(db_session, 9999)

    assert exc_info.value.code == 404
    assert str(exc_info.value) == "会话不存在"


def test_rename_conversation_trims(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())

    renamed = chat_service.rename_conversation(
        db_session, conversation.id, ConversationUpdateRequest(title="  新名字  ")
    )

    assert renamed.title == "新名字"


def test_rename_conversation_rejects_blank(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="原名")
    )

    with pytest.raises(BusinessError) as exc_info:
        chat_service.rename_conversation(
            db_session, conversation.id, ConversationUpdateRequest(title="   ")
        )

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "会话标题不能只包含空白"
    assert db_session.get(Conversation, conversation.id).title == "原名"


def test_rename_missing_conversation_prefers_404(db_session):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.rename_conversation(db_session, 9999, ConversationUpdateRequest(title="   "))

    assert exc_info.value.code == 404


def test_delete_conversation_removes_messages(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="待删")
    )
    _add_message(db_session, conversation, "user", "你好")
    _add_message(db_session, conversation, "assistant", "在的")

    chat_service.delete_conversation(db_session, conversation.id)

    assert db_session.get(Conversation, conversation.id) is None
    assert db_session.query(Message).count() == 0


def test_delete_conversation_missing_raises_404(db_session):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.delete_conversation(db_session, 9999)

    assert exc_info.value.code == 404
