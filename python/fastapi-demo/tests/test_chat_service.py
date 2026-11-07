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


class RecordingLLM:
    """记录收到的上下文，便于断言截断与排序；可注入异常验证回滚。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.received: list[list[dict[str, str]]] = []

    def chat(self, messages):
        self.received.append([dict(m) for m in messages])
        if self.error is not None:
            raise self.error
        return {"content": "好的", "model": "recording"}


def test_send_message_stores_both_messages(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())

    user_message, assistant_message = chat_service.send_message(
        db_session, conversation.id, "  你好  ", RecordingLLM()
    )

    assert user_message.content == "你好"
    assert user_message.role == "user"
    assert user_message.model is None
    assert assistant_message.content == "好的"
    assert assistant_message.role == "assistant"
    assert assistant_message.model == "recording"


def test_send_message_auto_titles_on_first_message(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())

    chat_service.send_message(db_session, conversation.id, "帮我给可乐定价", RecordingLLM())

    assert db_session.get(Conversation, conversation.id).title == "帮我给可乐定价"


def test_send_message_title_truncated_to_30_chars(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())

    chat_service.send_message(db_session, conversation.id, "很长的第一句话" * 10, RecordingLLM())

    title = db_session.get(Conversation, conversation.id).title
    assert len(title) == 30
    assert title == ("很长的第一句话" * 10)[:30]


def test_send_message_keeps_custom_title(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="我自己起的")
    )

    chat_service.send_message(db_session, conversation.id, "新消息", RecordingLLM())

    assert db_session.get(Conversation, conversation.id).title == "我自己起的"


def test_send_message_blank_content_raises_400(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())

    with pytest.raises(BusinessError) as exc_info:
        chat_service.send_message(db_session, conversation.id, "   ", RecordingLLM())

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "消息内容不能只包含空白"
    assert db_session.query(Message).count() == 0


def test_send_message_missing_conversation_returns_404_before_blank_check(db_session):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.send_message(db_session, 9999, "   ", RecordingLLM())

    assert exc_info.value.code == 404


def test_send_message_context_keeps_last_20_and_system(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())
    db_session.add(Message(conversation_id=conversation.id, role="system", content="你是助手"))
    for index in range(25):
        db_session.add(
            Message(conversation_id=conversation.id, role="user", content=f"历史{index}")
        )
    db_session.commit()
    llm = RecordingLLM()

    chat_service.send_message(db_session, conversation.id, "最新一句", llm)

    context = llm.received[0]
    assert context[0] == {"role": "system", "content": "你是助手"}
    # 1 条 system + 最近 20 条（含本次提问）
    assert len(context) == 21
    assert context[-1] == {"role": "user", "content": "最新一句"}
    assert context[1]["content"] == "历史6"


def test_send_message_rolls_back_when_model_fails(db_session):
    conversation = chat_service.create_conversation(db_session, ConversationCreateRequest())

    with pytest.raises(BusinessError) as exc_info:
        chat_service.send_message(
            db_session,
            conversation.id,
            "你好",
            RecordingLLM(error=BusinessError("模型挂了", code=502)),
        )

    assert exc_info.value.code == 502
    assert db_session.query(Message).count() == 0
    assert db_session.get(Conversation, conversation.id).title == "新会话"


def test_send_message_bumps_update_time(db_session):
    conversation = chat_service.create_conversation(
        db_session, ConversationCreateRequest(title="旧")
    )
    before = conversation.update_time

    chat_service.send_message(db_session, conversation.id, "你好", RecordingLLM())

    assert db_session.get(Conversation, conversation.id).update_time >= before
