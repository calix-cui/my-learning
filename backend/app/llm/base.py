"""模型客户端抽象：接口、统一错误与工厂。

业务代码只依赖这里的 `LLMClient` 协议，不关心背后是假实现还是真实服务。
"""

from collections.abc import Iterator
from typing import Any, Protocol, TypedDict

from app.common.exceptions import BusinessError


class ChatMessage(TypedDict):
    """一条发给模型的上下文消息。"""

    role: str
    content: str


class LLMReply(TypedDict):
    """模型返回。`model` 会写进 messages.model，便于区分 fake 与真实模型。"""

    content: str
    model: str


class ToolSpec(TypedDict):
    """一个可被模型调用的工具声明。

    `parameters` 是 JSON Schema；OpenAI 兼容接口要求它描述一个 object。
    """

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(TypedDict):
    """模型请求调用一次工具。

    `arguments` 保留上游返回的**原始 JSON 字符串**，不在这里解析——
    解析失败属于「模型输出了坏参数」，要作为 observation 回灌给模型让它自己纠错，
    而不是在这里抛异常中断整轮运行。
    """

    id: str
    name: str
    arguments: str


class LLMMessage(TypedDict, total=False):
    """带工具调用能力的消息。

    比 `ChatMessage` 多三样东西，都是工具循环需要的：
    - `tool_calls`：assistant 消息里模型请求的调用列表（回灌时必须原样带回）；
    - `tool_call_id`：tool 消息对应的调用 id，上游靠它配对；
    - `content`：允许为空串（模型只调工具、不说话时）。
    """

    role: str
    content: str
    tool_calls: list[dict[str, Any]]
    tool_call_id: str


class ToolCallReply(TypedDict):
    """一次带工具的补全结果。

    `tool_calls` 为空表示模型已经给出最终答复；否则要继续执行工具再来一轮。
    """

    content: str
    tool_calls: list[ToolCall]
    model: str
    finish_reason: str


class LLMError(BusinessError):
    """模型侧故障：默认 502，让调用方知道「不是我们的 bug，是上游」。"""

    def __init__(self, message: str = "模型服务不可用", code: int = 502):
        super().__init__(message, code=code)


class LLMTimeoutError(LLMError):
    """上游超时，单独给 504，便于前端提示「稍后再试」。"""

    def __init__(self, message: str = "模型服务超时"):
        super().__init__(message, code=504)


class LLMClient(Protocol):
    """模型客户端协议：普通补全、流式文本、带工具的一轮补全。"""

    def chat(self, messages: list[ChatMessage]) -> LLMReply: ...

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        """逐块产出回复文本；最后一块通常没有换行，由调用方负责拼接。"""
        ...

    def chat_with_tools(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> ToolCallReply:
        """带工具声明的一轮补全（原生 tool_calls，不做文本解析）。

        `tools` 为空时行为应等价于 `chat()`，只是返回结构统一。
        """
        ...
