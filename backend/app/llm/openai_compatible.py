"""OpenAI 兼容接口的客户端：一个 POST /chat/completions，用 httpx 直接打。

只依赖 `choices[0].message.content`，不绑定具体厂商（DeepSeek / OpenAI / 硅基流动等都兼容）。
"""

import json
import logging
from collections.abc import Iterator

import httpx

from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMMessage,
    LLMReply,
    LLMTimeoutError,
    ToolCall,
    ToolCallReply,
    ToolSpec,
)

logger = logging.getLogger(__name__)


def _default_client(timeout_seconds: float) -> httpx.Client:
    """构造 httpx.Client；环境变量里的代理配置有问题时退化为不读环境代理。

    实测：某些 shell / 工具链会把 NO_PROXY 写成 `localhost,::1,[::1]`，
    httpx 解析 `[::1]` 会抛 InvalidURL，导致服务一启动就崩。这里兜住它。
    """
    try:
        return httpx.Client(timeout=timeout_seconds)
    except (httpx.InvalidURL, ValueError) as exc:
        logger.warning("环境代理配置无法解析，改为忽略环境代理：%s", exc)
        return httpx.Client(timeout=timeout_seconds, trust_env=False)


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        # 允许注入 client，测试里用 MockTransport 拦截所有请求，不碰真实网络。
        self._client = client or _default_client(timeout_seconds)

    def _payload(self, messages: list[ChatMessage], *, stream: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        if stream:
            payload["stream"] = True
        return payload

    def _tool_payload(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> dict[str, object]:
        """带工具的一轮请求体。

        消息要按 OpenAI 的约定组装：assistant 的 `tool_calls` 原样带回，
        tool 消息带 `tool_call_id`，否则上游无法把结果和调用配对，会直接 400。
        """
        converted: list[dict[str, object]] = []
        for message in messages:
            role = message.get("role", "user")
            item: dict[str, object] = {"role": role, "content": message.get("content", "")}
            if message.get("tool_calls"):
                item["tool_calls"] = message["tool_calls"]
            if message.get("tool_call_id"):
                item["tool_call_id"] = message["tool_call_id"]
            converted.append(item)

        payload: dict[str, object] = {"model": self.model, "messages": converted}
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"],
                    },
                }
                for tool in tools
            ]
            payload["tool_choice"] = "auto"
        return payload

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _raise_for_status(self, status_code: int) -> None:
        if status_code in (401, 403):
            raise LLMError("模型服务鉴权失败，请检查 LLM_API_KEY")
        if status_code == 402:
            # DeepSeek 等厂商余额不足时返回 402，和鉴权失败区分开，便于排查
            raise LLMError("模型服务余额不足，请检查账户余额")
        if status_code == 429:
            raise LLMError("模型服务限流，请稍后重试")
        if status_code >= 400:
            # 不透传上游原文，避免把 key、内网地址等信息带到响应里。
            raise LLMError()

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        """按 OpenAI 的 SSE 约定逐块产出增量文本。"""
        try:
            with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=self._payload(messages, stream=True),
                headers=self._headers,
                timeout=self.timeout_seconds,
            ) as response:
                self._raise_for_status(response.status_code)
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[len("data:") :].strip()
                    if chunk == "[DONE]":
                        return
                    try:
                        payload = json.loads(chunk)
                        delta = payload["choices"][0]["delta"]
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        raise LLMError("模型返回格式无法解析") from exc
                    piece = delta.get("content")
                    if piece:
                        yield str(piece)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise LLMError() from exc

    def chat(self, messages: list[ChatMessage]) -> LLMReply:
        payload = self._payload(messages, stream=False)
        headers = self._headers
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise LLMError() from exc

        self._raise_for_status(response.status_code)

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型返回格式无法解析") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("模型返回内容为空")

        model = data.get("model") or self.model
        return LLMReply(content=content, model=str(model))

    def chat_with_tools(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> ToolCallReply:
        """一轮带工具的补全。

        不做任何文本解析：工具调用来自 `choices[0].message.tool_calls`，
        参数保持上游给的原始 JSON 字符串，交给工具层做 pydantic 校验。
        """
        payload = self._tool_payload(messages, tools)
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise LLMError() from exc

        self._raise_for_status(response.status_code)

        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型返回格式无法解析") from exc

        raw_calls = message.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            raise LLMError("模型返回格式无法解析")

        calls: list[ToolCall] = []
        for item in raw_calls:
            try:
                function = item["function"]
                calls.append(
                    ToolCall(
                        id=str(item.get("id") or f"call_{len(calls) + 1}"),
                        name=str(function["name"]),
                        # 参数可能是对象也可能是字符串，统一转成字符串交给工具层解析
                        arguments=_as_json_text(function.get("arguments")),
                    )
                )
            except (KeyError, TypeError, AttributeError) as exc:
                raise LLMError("模型返回格式无法解析") from exc

        content = message.get("content")
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise LLMError("模型返回格式无法解析")

        # 既没有文本也没有工具调用，说明上游返回了空结果，按失败处理
        if not calls and not content.strip():
            raise LLMError("模型返回内容为空")

        return ToolCallReply(
            content=content,
            tool_calls=calls,
            model=str(data.get("model") or self.model),
            finish_reason=str(choice.get("finish_reason") or ("tool_calls" if calls else "stop")),
        )


def _as_json_text(value: object) -> str:
    """把上游的 arguments 统一成字符串：对象序列化，字符串原样保留。"""
    if isinstance(value, str):
        return value
    if value is None:
        return "{}"
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise LLMError("模型返回格式无法解析") from exc
