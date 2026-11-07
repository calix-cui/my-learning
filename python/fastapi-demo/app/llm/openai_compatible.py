"""OpenAI 兼容接口的客户端：一个 POST /chat/completions，用 httpx 直接打。

只依赖 `choices[0].message.content`，不绑定具体厂商（DeepSeek / OpenAI / 硅基流动等都兼容）。
"""

import httpx

from app.llm.base import ChatMessage, LLMError, LLMReply, LLMTimeoutError


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
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def chat(self, messages: list[ChatMessage]) -> LLMReply:
        payload = {
            "model": self.model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
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

        if response.status_code in (401, 403):
            raise LLMError("模型服务鉴权失败，请检查 LLM_API_KEY")
        if response.status_code == 429:
            raise LLMError("模型服务限流，请稍后重试")
        if response.status_code >= 400:
            # 不透传上游原文，避免把 key、内网地址等信息带到响应里。
            raise LLMError()

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型返回格式无法解析") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("模型返回内容为空")

        model = data.get("model") or self.model
        return LLMReply(content=content, model=str(model))
