"""模型抽象层单测：不需要网络，也不需要 API key。"""

import json

import httpx
import pytest

from app.llm import build_llm, get_llm
from app.llm.base import LLMError, LLMTimeoutError
from app.llm.fake import FakeLLM, final_reply, tool_reply
from app.llm.openai_compatible import OpenAICompatibleClient


def test_fake_llm_echoes_last_user_message():
    llm = FakeLLM()

    reply = llm.chat(
        [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "在的"},
            {"role": "user", "content": "第二个问题"},
        ]
    )

    assert reply["content"] == "[fake] 收到：第二个问题"
    assert reply["model"] == "fake"


def test_fake_llm_stream_matches_chat_text():
    llm = FakeLLM()
    messages = [{"role": "user", "content": "你好"}]

    pieces = list(llm.stream(messages))

    assert len(pieces) > 1
    assert "".join(pieces) == llm.chat(messages)["content"]


def test_openai_compatible_stream_parses_deltas():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode()
        body = (
            'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, content=body.encode())

    pieces = list(_client(handler).stream([{"role": "user", "content": "你好"}]))

    assert pieces == ["你", "好"]
    assert '"stream":true' in captured["body"].replace(" ", "")


def test_openai_compatible_stream_maps_auth_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(LLMError) as exc_info:
        list(_client(handler).stream([{"role": "user", "content": "你好"}]))

    assert str(exc_info.value) == "模型服务鉴权失败，请检查 LLM_API_KEY"


def test_openai_compatible_stream_malformed_chunk():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data: {not json}\n\n")

    with pytest.raises(LLMError) as exc_info:
        list(_client(handler).stream([{"role": "user", "content": "你好"}]))

    assert str(exc_info.value) == "模型返回格式无法解析"


def test_fake_llm_honours_injected_error():
    llm = FakeLLM(error=LLMError("模型服务不可用"))

    with pytest.raises(LLMError) as exc_info:
        llm.chat([{"role": "user", "content": "你好"}])

    assert exc_info.value.code == 502


def test_get_llm_defaults_to_fake():
    assert isinstance(get_llm(), FakeLLM)
    assert isinstance(build_llm(), FakeLLM)


def _client(handler, **kwargs) -> OpenAICompatibleClient:
    transport = httpx.MockTransport(handler)
    return OpenAICompatibleClient(
        base_url="https://example.com/v1",
        api_key="k-123",
        model="test-model",
        client=httpx.Client(transport=transport),
        **kwargs,
    )


def test_openai_compatible_success():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "model": "test-model-0613",
                "choices": [{"message": {"role": "assistant", "content": "你好，我是模型"}}],
            },
        )

    reply = _client(handler).chat([{"role": "user", "content": "你好"}])

    assert reply["content"] == "你好，我是模型"
    assert reply["model"] == "test-model-0613"
    assert captured["url"] == "https://example.com/v1/chat/completions"
    assert captured["auth"] == "Bearer k-123"
    assert '"model":"test-model"' in captured["body"]


@pytest.mark.parametrize(
    ("status", "keyword"),
    [(401, "鉴权"), (403, "鉴权"), (429, "限流"), (500, "不可用")],
)
def test_openai_compatible_maps_http_errors(status, keyword):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "upstream detail"})

    with pytest.raises(LLMError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "你好"}])

    assert exc_info.value.code == 502
    assert keyword in str(exc_info.value)
    # 上游原文不能透传给用户
    assert "upstream detail" not in str(exc_info.value)


def test_openai_compatible_maps_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMTimeoutError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "你好"}])

    assert exc_info.value.code == 504


def test_openai_compatible_rejects_malformed_payload():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(LLMError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "你好"}])

    assert "格式" in str(exc_info.value)


def test_openai_compatible_rejects_empty_content():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    with pytest.raises(LLMError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "你好"}])

    assert "为空" in str(exc_info.value)


def test_client_falls_back_when_env_proxy_unparsable(monkeypatch):
    """NO_PROXY 里带 `[::1]` 时 httpx 会抛 InvalidURL；客户端应退化为忽略环境代理。"""
    from app.llm import openai_compatible as mod

    real_client_cls = httpx.Client
    calls: list[dict[str, object]] = []

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:  # noqa: ARG001
        calls.append(kwargs)
        if len(calls) == 1:
            raise httpx.InvalidURL("Invalid port: ':1]'")

        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return httpx.Response(200, json={})

        return real_client_cls(transport=httpx.MockTransport(handler), trust_env=False)

    monkeypatch.setattr(mod.httpx, "Client", fake_client)
    client = mod.OpenAICompatibleClient(base_url="https://example.com/v1", api_key="k", model="m")

    assert len(calls) == 2
    assert calls[1]["trust_env"] is False
    assert client._client is not None


# ---------------------------------------------------------------- 工具调用协议


def _calculator_tool() -> list:
    return [
        {
            "name": "calculator",
            "description": "计算四则运算表达式",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        }
    ]


def test_fake_chat_with_tools_follows_script_then_finishes():
    llm = FakeLLM(
        tool_script=[
            tool_reply("calculator", {"expression": "3**5"}),
            final_reply("243"),
        ]
    )
    messages = [{"role": "user", "content": "3 的 5 次方"}]

    first = llm.chat_with_tools(messages, _calculator_tool())
    second = llm.chat_with_tools(messages, _calculator_tool())
    third = llm.chat_with_tools(messages, _calculator_tool())

    assert first["tool_calls"] == [
        {"id": "call_1", "name": "calculator", "arguments": '{"expression": "3**5"}'}
    ]
    assert first["finish_reason"] == "tool_calls"
    assert second["tool_calls"] == []
    assert second["content"] == "243"
    # 剧本用完后回到普通回显，保证执行器一定能收尾
    assert third["tool_calls"] == []
    assert third["finish_reason"] == "stop"


def test_fake_chat_with_tools_records_seen_messages():
    llm = FakeLLM()
    messages = [{"role": "user", "content": "你好"}]

    llm.chat_with_tools(messages, [])

    assert llm.tool_calls_seen == [messages]


def test_openai_chat_with_tools_sends_tool_schema_and_parses_calls():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression": "2+3"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    reply = _client(handler).chat_with_tools(
        [{"role": "user", "content": "2+3 等于几"}], _calculator_tool()
    )

    body = json.loads(captured["body"])
    assert body["tools"][0]["type"] == "function"
    assert body["tools"][0]["function"]["name"] == "calculator"
    assert body["tools"][0]["function"]["parameters"]["required"] == ["expression"]
    assert body["tool_choice"] == "auto"

    assert reply["tool_calls"] == [
        {"id": "call_abc", "name": "calculator", "arguments": '{"expression": "2+3"}'}
    ]
    assert reply["content"] == ""
    assert reply["model"] == "deepseek-chat"
    assert reply["finish_reason"] == "tool_calls"


def test_openai_chat_with_tools_round_trip_includes_tool_messages():
    """回灌时必须原样带回 assistant.tool_calls 与 tool_call_id，否则上游 400。"""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "243"}}
                ]
            },
        )

    reply = _client(handler).chat_with_tools(
        [
            {"role": "user", "content": "3 的 5 次方"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "calculator", "arguments": '{"expression": "3**5"}'},
                    }
                ],
            },
            {"role": "tool", "content": "243", "tool_call_id": "call_1"},
        ],
        _calculator_tool(),
    )

    body = json.loads(captured["body"])
    assert body["messages"][1]["tool_calls"][0]["id"] == "call_1"
    assert body["messages"][2]["tool_call_id"] == "call_1"
    assert reply["content"] == "243"
    assert reply["tool_calls"] == []


def test_openai_chat_with_tools_accepts_object_arguments():
    """有的兼容网关把 arguments 直接给了对象，也要能收。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "function": {
                                        "name": "now",
                                        "arguments": {"timezone": "Asia/Shanghai"},
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
        )

    reply = _client(handler).chat_with_tools([{"role": "user", "content": "几点"}], [])
    assert reply["tool_calls"][0]["arguments"] == '{"timezone": "Asia/Shanghai"}'


def test_openai_chat_with_tools_rejects_empty_reply():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "  "}}]}
        )

    with pytest.raises(LLMError) as exc_info:
        _client(handler).chat_with_tools([{"role": "user", "content": "你好"}], [])

    assert str(exc_info.value) == "模型返回内容为空"


def test_openai_chat_with_tools_maps_timeout():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom")

    with pytest.raises(LLMTimeoutError):
        _client(handler).chat_with_tools([{"role": "user", "content": "你好"}], [])
