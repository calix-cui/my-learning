"""模型客户端抽象：接口、统一错误与工厂。

业务代码只依赖这里的 `LLMClient` 协议，不关心背后是假实现还是真实服务。
"""

from typing import Protocol, TypedDict

from app.common.exceptions import BusinessError


class ChatMessage(TypedDict):
    """一条发给模型的上下文消息。"""

    role: str
    content: str


class LLMReply(TypedDict):
    """模型返回。`model` 会写进 messages.model，便于区分 fake 与真实模型。"""

    content: str
    model: str


class LLMError(BusinessError):
    """模型侧故障：默认 502，让调用方知道「不是我们的 bug，是上游」。"""

    def __init__(self, message: str = "模型服务不可用", code: int = 502):
        super().__init__(message, code=code)


class LLMTimeoutError(LLMError):
    """上游超时，单独给 504，便于前端提示「稍后再试」。"""

    def __init__(self, message: str = "模型服务超时"):
        super().__init__(message, code=504)


class LLMClient(Protocol):
    """模型客户端协议。阶段 5/6 会加 `stream()` 与 `tool_calls`，届时扩展而不是推翻。"""

    def chat(self, messages: list[ChatMessage]) -> LLMReply: ...
