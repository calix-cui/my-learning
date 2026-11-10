"""执行器单测：事件序列、工具往返、预算与失败路径。

全部用 FakeLLM 的剧本驱动，不联网；`db_session` 是内存 SQLite。
"""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.agent.executor import MAX_STEPS, prepare_run, stream_run
from app.auth.service import register_user
from app.common.exceptions import BusinessError
from app.llm.base import ToolCallReply
from app.llm.fake import FakeLLM, final_reply, tool_reply
from app.models import AgentRun, AgentStep, Conversation, Message


def _setup(db: Session, email: str = "exec@example.com", title: str = "测试"):
    user = register_user(db, email, "password123")
    conversation = Conversation(user_id=user.id, title=title)
    db.add(conversation)
    db.commit()
    return user, conversation


def _drain(events: Iterator[dict]) -> list[dict]:
    return list(events)


def _types(events: list[dict]) -> list[str]:
    return [event["type"] for event in events]


def test_plain_answer_without_tools(db_session: Session):
    user, conversation = _setup(db_session)
    llm = FakeLLM()
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="你好"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )

    assert _types(events) == ["run_started", "run_finished"]
    assert events[-1]["steps"] == 2  # 用户消息 + 最终答复
    db_session.expire_all()
    assert db_session.get(AgentRun, run.id).status == "completed"
    kinds = [step.kind for step in db_session.query(AgentStep).filter_by(run_id=run.id)]
    assert kinds == ["user_message", "final_answer"]
    # 只写一条 assistant 消息，中间过程不进 messages
    messages_rows = db_session.query(Message).filter_by(conversation_id=conversation.id).all()
    assert [row.role for row in messages_rows] == ["user", "assistant"]
    # 首条消息自动命名
    # 标题取用户那句话，不是助手答复（否则侧栏会显示答案碎片）
    assert db_session.get(Conversation, conversation.id).title.startswith("你好")


def test_single_tool_round_trip(db_session: Session):
    user, conversation = _setup(db_session, email="exec-tool@example.com")
    llm = FakeLLM(
        tool_script=[
            tool_reply("calculator", {"expression": "3^5"}),
            final_reply("结果是 243"),
        ]
    )
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="3 的 5 次方"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )

    # 第二轮模型直接给出最终答复，所以没有单独的 assistant_text（那是「说完接着调工具」才有）
    assert _types(events) == ["run_started", "tool_call", "tool_result", "run_finished"]
    tool_result = next(event for event in events if event["type"] == "tool_result")
    assert tool_result["ok"] is True
    assert tool_result["content"] == "243"
    assert events[-1]["content"] == "结果是 243"

    kinds = [step.kind for step in db_session.query(AgentStep).filter_by(run_id=run.id)]
    assert kinds == ["user_message", "tool_call", "tool_result", "final_answer"]
    # 工具参数落库，便于前端「展开看参数」
    call_step = db_session.query(AgentStep).filter_by(run_id=run.id, kind="tool_call").one()
    assert call_step.tool_name == "calculator"
    result_step = db_session.query(AgentStep).filter_by(run_id=run.id, kind="tool_result").one()
    assert result_step.tool_args == {"expression": "3^5"}


def test_tool_failure_is_fed_back_to_model(db_session: Session):
    user, conversation = _setup(db_session, email="exec-fail@example.com")
    llm = FakeLLM(
        tool_script=[tool_reply("calculator", {"expression": "1/0"}), final_reply("不能除以零")]
    )
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="1/0"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )

    tool_result = next(event for event in events if event["type"] == "tool_result")
    assert tool_result["ok"] is False
    assert "不能除以零" in tool_result["content"]
    # 模型看到失败原因后仍能正常收尾
    assert events[-1]["type"] == "run_finished"
    assert events[-1]["content"] == "不能除以零"


def test_consecutive_tool_failures_abort(db_session: Session):
    user, conversation = _setup(db_session, email="exec-abort@example.com")
    bad = {"expression": "1/0"}
    # 每轮都请求同一个必然失败的工具，连续 3 次后执行器必须喊停
    llm = FakeLLM(
        tool_script=[
            tool_reply("calculator", bad, call_id="c1"),
            tool_reply("calculator", bad, call_id="c2"),
            tool_reply("calculator", bad, call_id="c3"),
        ]
    )
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="算三次"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )

    failures = [event for event in events if event["type"] == "tool_result" and not event["ok"]]
    assert len(failures) == 3
    assert events[-1]["type"] == "error"
    db_session.expire_all()
    failed = db_session.get(AgentRun, run.id)
    assert failed.status == "failed"
    assert "连续失败" in failed.error_message


def test_step_budget_aborts(db_session: Session):
    """模型一直请求工具：第 8 步之后必须停下。"""
    user, conversation = _setup(db_session, email="exec-budget@example.com")
    script: list[ToolCallReply] = [
        tool_reply("now", {}, call_id=f"c{index}") for index in range(MAX_STEPS + 2)
    ]
    llm = FakeLLM(tool_script=script)
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="一直调工具"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )

    assert events[-1]["type"] == "error"
    assert "超过最大步数" in events[-1]["message"]
    db_session.expire_all()
    assert db_session.get(AgentRun, run.id).status == "failed"


def test_unknown_tool_does_not_crash(db_session: Session):
    user, conversation = _setup(db_session, email="exec-unknown@example.com")
    llm = FakeLLM(tool_script=[tool_reply("rm_rf", {"path": "/"}), final_reply("没有这个工具")])
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="删库"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )

    tool_result = next(event for event in events if event["type"] == "tool_result")
    assert tool_result["ok"] is False
    assert "没有名为 rm_rf 的工具" in tool_result["content"]
    assert events[-1]["type"] == "run_finished"


def test_llm_failure_marks_run_failed(db_session: Session):
    from app.llm.base import LLMError

    user, conversation = _setup(db_session, email="exec-llm@example.com")
    llm = FakeLLM(error=LLMError("模型服务不可用"))
    _, run, messages, is_first = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="你好"
    )

    events = _drain(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=messages,
            llm=llm,
            is_first_message=is_first,
            user_id=user.id,
        )
    )

    assert events[0]["type"] == "run_started"
    assert events[-1] == {"type": "error", "code": 502, "message": "模型服务不可用"}
    db_session.expire_all()
    run_row = db_session.get(AgentRun, run.id)
    assert run_row.status == "failed"
    assert run_row.error_message == "模型服务不可用"
    # 失败时不能留下 assistant 消息
    roles = [
        row.role for row in db_session.query(Message).filter_by(conversation_id=conversation.id)
    ]
    assert roles == ["user"]


def test_missing_conversation_and_empty_content(db_session: Session):
    user, _ = _setup(db_session, email="exec-guard@example.com")
    # 不存在或不属于当前用户的会话一律 404
    with pytest.raises(BusinessError):
        prepare_run(db_session, user_id=user.id, conversation_id=99999, content="你好")
    with pytest.raises(BusinessError):
        prepare_run(db_session, user_id=user.id, conversation_id=1, content="   ")


def test_busy_conversation_rejected(db_session: Session):
    user, conversation = _setup(db_session, email="exec-busy@example.com")
    prepare_run(db_session, user_id=user.id, conversation_id=conversation.id, content="第一次")
    with pytest.raises(BusinessError) as busy:
        prepare_run(db_session, user_id=user.id, conversation_id=conversation.id, content="第二次")
    assert busy.value.code == 409
