"""假模型：默认实现，让链路在没有任何 key 的环境里也能跑通。

它只回显最后一条用户消息，行为完全确定，便于测试断言。
"""

import time
from collections.abc import Iterator
from typing import Any

from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMMessage,
    LLMReply,
    ToolCall,
    ToolCallReply,
    ToolSpec,
)


class FakeLLM:
    """确定性回显实现。

    - `delay_seconds`：模拟慢请求，用于验证前端的「正在回复…」；
    - `error`：注入异常，用于验证 502/504 的错误映射。
    """

    def __init__(
        self,
        model: str = "fake",
        delay_seconds: float = 0.0,
        error: Exception | None = None,
        tool_script: list[ToolCallReply] | None = None,
    ) -> None:
        self.model = model
        self.delay_seconds = delay_seconds
        self.error = error
        # 工具循环的剧本：每次 chat_with_tools 消费一条，用完之后退回普通回显
        # （即不再请求工具）——这样执行器能在第 N 步自然收尾。
        self._tool_script = list(tool_script or [])
        self.tool_calls_seen: list[list[LLMMessage]] = []

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

    def chat_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolSpec],  # noqa: ARG002 —— 假实现不看工具声明，只照剧本演
    ) -> ToolCallReply:
        """按剧本返回：先给若干轮 `tool_calls`，剧本用完后返回最终文本。

        剧本里每条都是 dict（`ToolCallReply`），可以只写需要的字段；
        为了让测试读起来清楚，鼓励用模块函数 `tool_reply()` / `final_reply()` 构造。
        """
        if self.error is not None:
            raise self.error
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        self.tool_calls_seen.append(messages)

        if self._tool_script:
            scripted = self._tool_script.pop(0)
            return ToolCallReply(
                content=str(scripted.get("content", "")),
                tool_calls=list(scripted.get("tool_calls", [])),
                model=str(scripted.get("model") or self.model),
                finish_reason=str(scripted.get("finish_reason") or _reason_of(scripted)),
            )

        # 剧本用完：把最后一条 user 文本回显出来，且不再请求工具——循环到此收尾。
        plain = self._full_text(messages)  # type: ignore[arg-type]
        return ToolCallReply(content=plain, tool_calls=[], model=self.model, finish_reason="stop")

    def _full_text(self, messages: list[ChatMessage]) -> str:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"[{self.model}] 收到：{last_user}"


def _reason_of(reply: ToolCallReply) -> str:
    return "tool_calls" if reply.get("tool_calls") else "stop"


def tool_reply(
    name: str,
    arguments: dict[str, Any] | str,
    *,
    call_id: str = "call_1",
    content: str = "",
) -> ToolCallReply:
    """剧本条目：请求调用一个工具。`arguments` 传 dict 会转成 JSON 字符串。"""
    raw = arguments if isinstance(arguments, str) else _dumps(arguments)
    return ToolCallReply(
        content=content,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=raw)],
        model="fake",
        finish_reason="tool_calls",
    )


def final_reply(content: str) -> ToolCallReply:
    """剧本条目：直接给最终答复，不请求工具。"""
    return ToolCallReply(content=content, tool_calls=[], model="fake", finish_reason="stop")


def _dumps(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


__all__ = ["FakeLLM", "LLMError", "final_reply", "tool_reply"]
