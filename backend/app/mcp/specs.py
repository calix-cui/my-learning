"""MCP 服务器的描述结构与安全校验。

这一层刻意不依赖数据库与 SDK：`McpServerSpec` 既可以由 `mcp_servers` 表构造，
也可以在测试里手写。校验放在这里，接口层与市场页共用同一套规则。
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from app.mcp.errors import McpError, McpErrorKind

Transport = Literal["stdio", "http"]

# 允许本地起的可执行文件。用户填什么由这里兜底——市场页只给这四个模板，
# 自定义条目也要过这一关，避免把任意命令写进配置（等于给了一个远程执行入口）。
ALLOWED_COMMANDS = frozenset({"npx", "uvx", "node", "python", "python3", "uv"})

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")

# 不允许指向内网/本机：远端服务器应当是可公开访问的 HTTPS 端点。
_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"})


@dataclass(frozen=True)
class McpServerSpec:
    """一个 MCP server 的接入参数。"""

    slug: str
    display_name: str
    transport: Transport
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_spec(self)

    @property
    def is_stdio(self) -> bool:
        return self.transport == "stdio"

    def redacted(self) -> dict[str, Any]:
        """给接口/日志用的脱敏表示：env 只留键名，不留值。"""
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "transport": self.transport,
            "command": self.command,
            "args": list(self.args),
            "url": self.url,
            "env_keys": sorted(self.env),
        }


@dataclass(frozen=True)
class McpToolInfo:
    """列出来的工具。`read_only` 来自 `annotations.readOnlyHint`，只用于降级到 READ。"""

    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool = False


@dataclass(frozen=True)
class McpCallResult:
    """一次工具调用的结果，已经把 SDK 的 content 拍平成文本。"""

    ok: bool
    text: str
    raw: list[dict[str, Any]] = field(default_factory=list)


def validate_spec(spec: McpServerSpec) -> None:
    """校验合法性，不合法抛 `McpError(CONFIG)`。"""
    if not SLUG_PATTERN.match(spec.slug):
        raise McpError(McpErrorKind.CONFIG, "服务器标识只能用 1–32 位小写字母、数字与连字符")

    if spec.transport == "stdio":
        _validate_stdio(spec)
    elif spec.transport == "http":
        _validate_http(spec)
    else:  # pragma: no cover - Transport 是 Literal，写错类型时兜底
        raise McpError(McpErrorKind.CONFIG, f"不支持的传输方式：{spec.transport}")


def _validate_stdio(spec: McpServerSpec) -> None:
    if not spec.command:
        raise McpError(McpErrorKind.CONFIG, "本地服务器必须指定启动命令")
    if spec.command not in ALLOWED_COMMANDS:
        allowed = "、".join(sorted(ALLOWED_COMMANDS))
        raise McpError(McpErrorKind.CONFIG, f"启动命令只允许这些：{allowed}")
    if spec.url:
        raise McpError(McpErrorKind.CONFIG, "本地服务器不需要 url")
    for key, value in spec.env.items():
        if not key.isidentifier():
            raise McpError(McpErrorKind.CONFIG, f"环境变量名不合法：{key}")
        if "\n" in value or "\x00" in value:
            raise McpError(McpErrorKind.CONFIG, f"环境变量 {key} 的值里不能有换行或空字符")


def _validate_http(spec: McpServerSpec) -> None:
    if spec.command:
        raise McpError(McpErrorKind.CONFIG, "远程服务器不需要启动命令")
    if not spec.url:
        raise McpError(McpErrorKind.CONFIG, "远程服务器必须填写 url")

    parsed = urlparse(spec.url)
    if parsed.scheme != "https":
        raise McpError(McpErrorKind.CONFIG, "远程服务器只支持 https")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise McpError(McpErrorKind.CONFIG, "url 缺少主机名")
    if host in _BLOCKED_HOSTS:
        raise McpError(McpErrorKind.CONFIG, "不允许指向本机地址")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise McpError(McpErrorKind.CONFIG, "不允许指向内网地址")
