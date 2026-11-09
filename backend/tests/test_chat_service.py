"""会话服务层测试：内存 SQLite，覆盖增删改查、分页排序与级联删除。"""

import pytest

from app.common.exceptions import BusinessError
from app.llm import LLMError
from app.models import Conversation, Message
from app.schemas.chat import ConversationCreateRequest, ConversationUpdateRequest
from app.services import chat_service


def _add_message(db, conversation: Conversation, role: str, content: str) -> Message:
    message = Message(conversation_id=conversation.id, role=role, content=content)
    db.add(message)
    db.commit()
    return message


def test_create_conversation_uses_default_title(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    assert conversation.title == "新会话"
    assert conversation.agent_key == "default"
    assert conversation.id > 0
    assert conversation.update_time is not None


def test_create_conversation_trims_title(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="  商品定价  ")
    )

    assert conversation.title == "商品定价"


def test_create_conversation_blank_title_falls_back_to_default(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="   ")
    )

    assert conversation.title == "新会话"


def test_list_conversations_orders_by_update_time_desc(db_session, user):
    first = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="早")
    )
    second = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="晚")
    )
    _add_message(db_session, first, "user", "让 first 变成最近活动")
    # update_time 有 onupdate，写入消息不会自动改会话，这里手动触发一次更新
    first.title = "早（已更新）"
    db_session.commit()

    page = chat_service.list_conversations(db_session, user.id)

    assert page["total"] == 2
    assert [item["title"] for item in page["items"]] == ["早（已更新）", "晚"]
    assert second.id != first.id


def test_list_conversations_counts_messages(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="有消息")
    )
    _add_message(db_session, conversation, "user", "你好")
    _add_message(db_session, conversation, "assistant", "在的")
    chat_service.create_conversation(db_session, user.id, ConversationCreateRequest(title="空会话"))

    page = chat_service.list_conversations(db_session, user.id)

    counts = {item["title"]: item["message_count"] for item in page["items"]}
    assert counts == {"有消息": 2, "空会话": 0}


def test_list_conversations_paginates(db_session, user):
    for index in range(3):
        chat_service.create_conversation(
            db_session, user.id, ConversationCreateRequest(title=f"会话{index}")
        )

    page = chat_service.list_conversations(db_session, user.id, page=2, page_size=2)

    assert page["total"] == 3
    assert len(page["items"]) == 1
    assert page["page"] == 2
    assert page["page_size"] == 2


def test_get_conversation_returns_messages_in_order(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="顺序")
    )
    _add_message(db_session, conversation, "user", "第一句")
    _add_message(db_session, conversation, "assistant", "第二句")

    loaded = chat_service.get_conversation(db_session, user.id, conversation.id)

    assert [m.content for m in loaded.messages] == ["第一句", "第二句"]


def test_get_conversation_missing_raises_404(db_session, user):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.get_conversation(db_session, user.id, 9999)

    assert exc_info.value.code == 404
    assert str(exc_info.value) == "会话不存在"


def test_rename_conversation_trims(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    renamed = chat_service.rename_conversation(
        db_session, user.id, conversation.id, ConversationUpdateRequest(title="  新名字  ")
    )

    assert renamed.title == "新名字"


def test_rename_conversation_rejects_blank(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="原名")
    )

    with pytest.raises(BusinessError) as exc_info:
        chat_service.rename_conversation(
            db_session, user.id, conversation.id, ConversationUpdateRequest(title="   ")
        )

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "会话标题不能只包含空白"
    assert db_session.get(Conversation, conversation.id).title == "原名"


def test_rename_missing_conversation_prefers_404(db_session, user):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.rename_conversation(
            db_session, user.id, 9999, ConversationUpdateRequest(title="   ")
        )

    assert exc_info.value.code == 404


def test_delete_conversation_removes_messages(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="待删")
    )
    _add_message(db_session, conversation, "user", "你好")
    _add_message(db_session, conversation, "assistant", "在的")

    chat_service.delete_conversation(db_session, user.id, conversation.id)

    assert db_session.get(Conversation, conversation.id) is None
    assert db_session.query(Message).count() == 0


def test_delete_conversation_missing_raises_404(db_session, user):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.delete_conversation(db_session, user.id, 9999)

    assert exc_info.value.code == 404


class RecordingLLM:
    """记录收到的上下文，便于断言截断与排序；可注入异常验证回滚。"""

    def __init__(self, error: Exception | None = None, pieces: list[str] | None = None) -> None:
        self.error = error
        self.pieces = pieces if pieces is not None else ["好", "的"]
        self.model = "recording"
        self.received: list[list[dict[str, str]]] = []

    def chat(self, messages):
        self.received.append([dict(m) for m in messages])
        if self.error is not None:
            raise self.error
        return {"content": "好的", "model": "recording"}

    def stream(self, messages):
        self.received.append([dict(m) for m in messages])
        if self.error is not None:
            raise self.error
        yield from self.pieces


def test_send_message_stores_both_messages(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    user_message, assistant_message = chat_service.send_message(
        db_session, user.id, conversation.id, "  你好  ", RecordingLLM()
    )

    assert user_message.content == "你好"
    assert user_message.role == "user"
    assert user_message.model is None
    assert assistant_message.content == "好的"
    assert assistant_message.role == "assistant"
    assert assistant_message.model == "recording"


def test_send_message_auto_titles_on_first_message(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    chat_service.send_message(
        db_session, user.id, conversation.id, "帮我给可乐定价", RecordingLLM()
    )

    assert db_session.get(Conversation, conversation.id).title == "帮我给可乐定价"


def test_send_message_title_truncated_to_30_chars(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    chat_service.send_message(
        db_session, user.id, conversation.id, "很长的第一句话" * 10, RecordingLLM()
    )

    title = db_session.get(Conversation, conversation.id).title
    assert len(title) == 30
    assert title == ("很长的第一句话" * 10)[:30]


def test_send_message_keeps_custom_title(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="我自己起的")
    )

    chat_service.send_message(db_session, user.id, conversation.id, "新消息", RecordingLLM())

    assert db_session.get(Conversation, conversation.id).title == "我自己起的"


def test_send_message_blank_content_raises_400(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    with pytest.raises(BusinessError) as exc_info:
        chat_service.send_message(db_session, user.id, conversation.id, "   ", RecordingLLM())

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "消息内容不能只包含空白"
    assert db_session.query(Message).count() == 0


def test_send_message_missing_conversation_returns_404_before_blank_check(db_session, user):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.send_message(db_session, user.id, 9999, "   ", RecordingLLM())

    assert exc_info.value.code == 404


def test_send_message_context_keeps_last_20_and_system(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )
    db_session.add(Message(conversation_id=conversation.id, role="system", content="你是助手"))
    for index in range(25):
        db_session.add(
            Message(conversation_id=conversation.id, role="user", content=f"历史{index}")
        )
    db_session.commit()
    llm = RecordingLLM()

    chat_service.send_message(db_session, user.id, conversation.id, "最新一句", llm)

    context = llm.received[0]
    assert context[0] == {"role": "system", "content": "你是助手"}
    # 1 条 system + 最近 20 条（含本次提问）
    assert len(context) == 21
    assert context[-1] == {"role": "user", "content": "最新一句"}
    assert context[1]["content"] == "历史6"


def test_send_message_rolls_back_when_model_fails(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    with pytest.raises(BusinessError) as exc_info:
        chat_service.send_message(
            db_session,
            user.id,
            conversation.id,
            "你好",
            RecordingLLM(error=BusinessError("模型挂了", code=502)),
        )

    assert exc_info.value.code == 502
    assert db_session.query(Message).count() == 0
    assert db_session.get(Conversation, conversation.id).title == "新会话"


def test_send_message_bumps_update_time(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest(title="旧")
    )
    before = conversation.update_time

    chat_service.send_message(db_session, user.id, conversation.id, "你好", RecordingLLM())

    assert db_session.get(Conversation, conversation.id).update_time >= before


def _drain(events):
    return list(events)


def test_prepare_stream_writes_user_message_and_context(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    _, user_message, context, is_first = chat_service.prepare_stream(
        db_session, user.id, conversation.id, "  你好  "
    )

    assert user_message.id > 0
    assert user_message.content == "你好"
    assert is_first is True
    assert [m["role"] for m in context] == ["user"]


def test_prepare_stream_blank_content_raises_400(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )

    with pytest.raises(BusinessError) as exc_info:
        chat_service.prepare_stream(db_session, user.id, conversation.id, "   ")

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "消息内容不能只包含空白"


def test_prepare_stream_missing_conversation_raises_404(db_session, user):
    with pytest.raises(BusinessError) as exc_info:
        chat_service.prepare_stream(db_session, user.id, 9999, "你好")

    assert exc_info.value.code == 404


def test_stream_reply_emits_meta_delta_done_and_persists(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )
    prepared = chat_service.prepare_stream(db_session, user.id, conversation.id, "帮我给可乐定价")

    events = _drain(chat_service.stream_reply(db_session, *prepared, RecordingLLM()))

    assert [e["type"] for e in events] == ["meta", "delta", "delta", "done"]
    assert events[0]["user_message"]["content"] == "帮我给可乐定价"
    assert "".join(e["content"] for e in events if e["type"] == "delta") == "好的"
    assert events[-1]["assistant_message"]["content"] == "好的"
    assert events[-1]["message_count"] == 2
    assert db_session.query(Message).count() == 2


def test_stream_reply_auto_titles_on_first_message(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )
    prepared = chat_service.prepare_stream(db_session, user.id, conversation.id, "帮我给可乐定价")

    events = _drain(chat_service.stream_reply(db_session, *prepared, RecordingLLM()))

    assert events[-1]["conversation_title"] == "帮我给可乐定价"
    assert db_session.get(Conversation, conversation.id).title == "帮我给可乐定价"


def test_stream_reply_error_event_rolls_back(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )
    prepared = chat_service.prepare_stream(db_session, user.id, conversation.id, "你好")

    events = _drain(
        chat_service.stream_reply(db_session, *prepared, RecordingLLM(error=LLMError()))
    )

    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == 502
    assert db_session.query(Message).count() == 0


def test_stream_reply_empty_reply_becomes_error(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )
    prepared = chat_service.prepare_stream(db_session, user.id, conversation.id, "你好")

    events = _drain(chat_service.stream_reply(db_session, *prepared, RecordingLLM(pieces=["  "])))

    assert events[-1]["type"] == "error"
    assert events[-1]["message"] == "模型返回内容为空"
    assert db_session.query(Message).count() == 0


def test_stream_reply_client_disconnect_rolls_back(db_session, user):
    conversation = chat_service.create_conversation(
        db_session, user.id, ConversationCreateRequest()
    )
    prepared = chat_service.prepare_stream(db_session, user.id, conversation.id, "你好")
    events = chat_service.stream_reply(db_session, *prepared, RecordingLLM())

    next(events)  # 只读一条 meta 就断开
    events.close()

    assert db_session.query(Message).count() == 0
