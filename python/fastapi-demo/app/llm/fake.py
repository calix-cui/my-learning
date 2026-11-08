"""假模型：默认实现，让链路在没有任何 key 的环境里也能跑通。

它只回显最后一条用户消息，行为完全确定，便于测试断言。
"""

import time
from collections.abc import Iterator

from app.llm.base import ChatMessage, LLMError, LLMReply


class FakeLLM:
    """确定性回显实现。

    - `delay_seconds`：模拟慢请求，用于验证前端的「正在回复…」；
    - `error`：注入异常，用于验证 502/504 的错误映射。
    """

    def __init__(
        self, model: str = "fake", delay_seconds: float = 0.0, error: Exception | None = None
    ) -> None:
        self.model = model
        self.delay_seconds = delay_seconds
        self.error = error

    def chat(self, messages: list[ChatMessage]) -> LLMReply:
        if self.error is not None:
            raise self.error
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return LLMReply(content=self._full_text(messages), model=self.model)

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        """按固定步长切片，模拟逐块返回；拼起来与 chat() 的结果完全一致。"""
        if self.error is not None:
            raise self.error
        text = self._full_text(messages)
        step = 4
        for index in range(0, len(text), step):
            if self.delay_seconds:
                time.sleep(self.delay_seconds)
            yield text[index : index + step]

    def _full_text(self, messages: list[ChatMessage]) -> str:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"[{self.model}] 收到：{last_user}"


__all__ = ["FakeLLM", "LLMError"]
