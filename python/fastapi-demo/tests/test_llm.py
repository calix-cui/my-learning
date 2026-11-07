"""模型抽象层单测：不需要网络，也不需要 API key。"""

import httpx
import pytest

from app.llm import build_llm, get_llm
from app.llm.base import LLMError, LLMTimeoutError
from app.llm.fake import FakeLLM
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
