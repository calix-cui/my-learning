"""工具层单测：参数校验、安全边界、用户隔离。"""

import pytest
from sqlalchemy.orm import Session

from app.agent.tools import build_registry
from app.agent.tools.base import run_tool
from app.agent.tools.calculator import CalculatorTool, evaluate
from app.agent.tools.clock import NowTool
from app.agent.tools.history import SearchConversationsTool
from app.auth.service import register_user
from app.models import Conversation


def test_calculator_basic_and_power_notation():
    assert evaluate("2+3") == 5
    # 模型常把幂写成 ^；必须当幂处理，而不是按位异或
    assert evaluate("3^5") == 243
    assert evaluate("(12+8)*3") == 60
    assert evaluate("7/2") == 3.5


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('ls')",
        "open('/etc/passwd').read()",
        "9**9**9",
        "1/0",
        "abc",
        "1+",
    ],
)
def test_calculator_rejects_dangerous_or_invalid(expression):
    result = run_tool(CalculatorTool(), f'{{"expression": "{expression}"}}', user_id=1)
    assert result["ok"] is False
    assert result["content"]


def test_calculator_reports_syntax_and_empty_as_tool_errors():
    assert run_tool(CalculatorTool(), '{"expression": ""}', user_id=1)["ok"] is False
    assert run_tool(CalculatorTool(), '{"expression": "1+"}', user_id=1)["ok"] is False


def test_now_tool_returns_timezone_and_weekday():
    result = run_tool(NowTool(), '{"timezone": "UTC"}', user_id=1)
    assert result["ok"] is True
    assert "UTC" in result["content"]
    assert "星期" in result["content"]


def test_now_tool_rejects_unknown_timezone():
    result = run_tool(NowTool(), '{"timezone": "Mars/Olympus"}', user_id=1)
    assert result["ok"] is False
    assert "未知时区" in result["content"]


def test_search_conversations_only_sees_own_rows(db_session: Session):
    alice = register_user(db_session, "tool-alice@example.com", "password123")
    bob = register_user(db_session, "tool-bob@example.com", "password123")
    db_session.add_all(
        [
            Conversation(user_id=alice.id, title="部署方案讨论"),
            Conversation(user_id=bob.id, title="部署方案讨论（别人的）"),
        ]
    )
    db_session.commit()

    tool = SearchConversationsTool(db_session)
    result = run_tool(tool, '{"keyword": "部署"}', user_id=alice.id)

    assert result["ok"] is True
    assert "找到 1 个相关会话" in result["content"]
    # 绝不能出现另一个用户的标题
    assert "别人的" not in result["content"]


def test_search_conversations_escapes_like_wildcards(db_session: Session):
    user = register_user(db_session, "tool-like@example.com", "password123")
    db_session.add(Conversation(user_id=user.id, title="100% 完成"))
    db_session.commit()

    tool = SearchConversationsTool(db_session)
    assert "找到 1 个" in run_tool(tool, '{"keyword": "%"}', user_id=user.id)["content"]


def test_search_conversations_empty_result(db_session: Session):
    user = register_user(db_session, "tool-empty@example.com", "password123")
    tool = SearchConversationsTool(db_session)
    result = run_tool(tool, '{"keyword": "不存在"}', user_id=user.id)
    assert result["ok"] is True
    assert "没有找到" in result["content"]


def test_registry_executes_and_reports_unknown_tool(db_session: Session):
    registry = build_registry(db_session)

    assert registry.names() == ["calculator", "now", "search_conversations"]
    assert registry.has("calculator")
    assert registry.execute("calculator", '{"expression": "2^10"}', user_id=1)["content"] == "1024"

    unknown = registry.execute("rm_rf", "{}", user_id=1)
    assert unknown["ok"] is False
    assert "没有名为 rm_rf 的工具" in unknown["content"]


def test_registry_rejects_malformed_arguments(db_session: Session):
    registry = build_registry(db_session)
    result = registry.execute("calculator", "not-json", user_id=1)
    assert result["ok"] is False
    assert result["content"] == "工具参数不是合法 JSON"


def test_specs_are_json_schemas(db_session: Session):
    registry = build_registry(db_session)
    specs = {spec["name"]: spec for spec in registry.specs()}
    assert specs["calculator"]["parameters"]["required"] == ["expression"]
    assert specs["search_conversations"]["parameters"]["properties"]["limit"]["maximum"] == 10
