"""MCP 工具市场的请求/响应结构。

三个刻意的边界：
- 请求里**没有** `slug` 以外的必填项，接入一个市场条目只要 `{slug, path?}`；
- 响应里**永不回显** env 明文，只给键名（`env_keys`）；
- `tools` 列表只在「当前有连接」时才有内容，不为了展示去连一次服务器。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Transport = Literal["stdio", "http"]


class CatalogItem(BaseModel):
    """市场里的一张卡片。"""

    slug: str
    display_name: str
    summary: str
    transport: Transport
    tags: list[str] = Field(default_factory=list)
    icon: str = "sparkle"
    requires_path: bool = False
    docs_url: str | None = None
    updated: str
    installed_id: int | None = Field(default=None, description="已接入时的服务器 id")
    last_status: str | None = Field(default=None, description="已接入时的最近连接状态")


class CatalogResponse(BaseModel):
    items: list[CatalogItem] = Field(default_factory=list)
    updated: str


class McpToolBrief(BaseModel):
    name: str
    remote_name: str
    description: str = ""
    read_only: bool = False


class McpServerItem(BaseModel):
    id: int
    slug: str
    display_name: str
    transport: Transport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env_keys: list[str] = Field(default_factory=list)
    enabled: bool
    last_status: str
    last_error: str | None = None
    tool_count: int = 0
    last_connected_time: datetime | None = None
    create_time: datetime | None = None
    tools: list[McpToolBrief] = Field(
        default_factory=list, description="已连接时缓存的工具清单，未连接为空"
    )


class McpServerListResponse(BaseModel):
    items: list[McpServerItem] = Field(default_factory=list)


class McpServerCreateRequest(BaseModel):
    """接入一台服务器：内置条目给 slug（+ path/env），自定义条目补齐 transport 等字段。"""

    slug: str = Field(min_length=1, max_length=32)
    path: str | None = Field(default=None, max_length=512, description="需要目录的条目用它填")
    env: dict[str, str] | None = Field(default=None, description="只存密文，不回显")
    # 以下仅自定义条目用；市场条目会忽略它们
    display_name: str | None = Field(default=None, max_length=64)
    transport: Transport | None = None
    command: str | None = Field(default=None, max_length=32)
    args: list[str] | None = None
    url: str | None = Field(default=None, max_length=255)


class McpServerUpdateRequest(BaseModel):
    enabled: bool | None = None
    display_name: str | None = Field(default=None, max_length=64)
    args: list[str] | None = None
    url: str | None = Field(default=None, max_length=255)
    env: dict[str, str] | None = None


class McpTestResponse(BaseModel):
    ok: bool
    message: str
    tools: list[McpToolBrief] = Field(default_factory=list)
    duration_ms: int = 0


__all__ = [
    "CatalogItem",
    "CatalogResponse",
    "McpServerCreateRequest",
    "McpServerItem",
    "McpServerListResponse",
    "McpServerUpdateRequest",
    "McpTestResponse",
    "McpToolBrief",
]
