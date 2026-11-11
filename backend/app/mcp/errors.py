"""MCP 相关的错误类型。

设计原则：对外只抛 `McpError`，把 SDK 的异常（`anyio` 超时、`httpx2` 连接错误、
子进程退出）统一翻译成「哪种失败 + 能否重试 + 给人看的一句话」，上层不必认识 SDK。
"""

from __future__ import annotations

from enum import StrEnum


class McpErrorKind(StrEnum):
    """失败的种类，决定用户看到什么、要不要重试。"""

    CONFIG = "config"  # 配置不合法（命令不在白名单、url 不是 https）
    CONNECT = "connect"  # 连不上（子进程起不来、远端拒绝）
    TIMEOUT = "timeout"  # 握手/列工具/调用超时
    PROTOCOL = "protocol"  # 握手失败、返回结构不符合协议
    TOOL = "tool"  # 工具本身报错（`isError`）——通常不算异常，仅用于日志


class McpError(Exception):
    """MCP 调用失败。

    `kind` 给程序判断，`message` 给人看（中文、可直接进前端提示）。
    """

    def __init__(self, kind: McpErrorKind, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.detail = detail

    @property
    def retryable(self) -> bool:
        """连不上 / 超时可以重试；配置错误与协议错误重试也没用。"""
        return self.kind in (McpErrorKind.CONNECT, McpErrorKind.TIMEOUT)

    def __str__(self) -> str:
        return self.message if self.detail is None else f"{self.message}（{self.detail}）"
