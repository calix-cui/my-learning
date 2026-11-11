"""MCP 工具市场的业务逻辑：清单、接入、启停、删除、试连。

三条纪律：
1. **校验只有一套**：用户输入一律先变成 `McpServerSpec`（`app/mcp/specs.py`），
   那里有命令白名单、https-only、内网拦截；服务层不重复写规则。
2. **env 只存密文**：复用 `app/common/crypto`（与模型 Key 同一套 Fernet），
   读出时解密给连接用，接口只回键名。
3. **改配置要断连接**：用户改了 args/url/env 后必须 `manager.forget()`，
   否则下次 run 连的还是老进程。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common import crypto
from app.common.exceptions import BusinessError
from app.mcp.catalog import CATALOG, CATALOG_UPDATED, find_entry
from app.mcp.errors import McpError
from app.mcp.manager import get_manager, probe
from app.mcp.specs import McpServerSpec, McpToolInfo
from app.models import McpServer
from app.models.mcp_server import STATUS_ERROR, STATUS_OK, STATUS_UNKNOWN
from app.schemas.mcp import (
    CatalogItem,
    CatalogResponse,
    McpServerCreateRequest,
    McpServerItem,
    McpServerListResponse,
    McpServerUpdateRequest,
    McpTestResponse,
    McpToolBrief,
)

# 一台服务器最多缓存多少个工具名，防止某个服务器列出上千个把响应撑爆
MAX_TOOL_BRIEFS = 200


def _briefs(tools: list[McpToolInfo], *, slug: str) -> list[McpToolBrief]:
    from app.mcp.source import tool_name

    return [
        McpToolBrief(
            name=tool_name(slug, info.name),
            remote_name=info.name,
            description=info.description,
            read_only=info.read_only,
        )
        for info in tools[:MAX_TOOL_BRIEFS]
    ]


def _encrypt_env(env: dict[str, str] | None) -> str | None:
    """空 env 存 NULL（不是空对象），读的时候才好判断「有没有配过」。"""
    if not env:
        return None
    try:
        return crypto.encrypt(json.dumps(env, ensure_ascii=False, sort_keys=True))
    except crypto.SecretNotConfiguredError as exc:
        raise BusinessError(f"保存环境变量需要先配置 APP_SECRET_KEY：{exc}") from exc


def _decrypt_env(row: McpServer) -> dict[str, str]:
    if not row.env_ciphertext:
        return {}
    try:
        raw = crypto.decrypt(row.env_ciphertext)
    except crypto.SecretNotConfiguredError as exc:
        raise BusinessError(f"无法读取已保存的环境变量：{exc}") from exc
    try:
        value = json.loads(raw)
    except ValueError as exc:  # 密文被人手改坏
        raise BusinessError("环境变量已损坏，请重新填写") from exc
    return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else {}


def spec_of_row(row: McpServer) -> McpServerSpec:
    """把一行变成可连接的 spec（含解密后的 env）。"""
    return McpServerSpec(**row.spec_payload, env=_decrypt_env(row))


def _get_row(db: Session, user_id: int, server_id: int) -> McpServer:
    row = db.scalar(
        select(McpServer).where(McpServer.id == server_id, McpServer.user_id == user_id)
    )
    if row is None:
        # 越权与不存在返回同一个响应，不泄露「这条记录存在」
        raise BusinessError("MCP 服务器不存在", code=404)
    return row


def _to_item(row: McpServer) -> McpServerItem:
    tools = get_manager().cached_tools(row.id)
    return McpServerItem(
        id=row.id,
        slug=row.slug,
        display_name=row.display_name,
        transport=row.transport,  # type: ignore[arg-type]
        command=row.command,
        args=list(row.args or []),
        url=row.url,
        env_keys=sorted(_decrypt_env_safe(row)),
        enabled=row.enabled,
        last_status=row.last_status,
        last_error=row.last_error,
        tool_count=row.tool_count,
        last_connected_time=row.last_connected_time,
        create_time=row.create_time,
        tools=_briefs(tools, slug=row.slug),
    )


def _decrypt_env_safe(row: McpServer) -> dict[str, str]:
    """列表页不该因为密钥缺失整体 500：读不出来就当作没有 env。"""
    try:
        return _decrypt_env(row)
    except BusinessError:
        return {}


# ---------- 读 ----------


def list_catalog(db: Session, user_id: int) -> CatalogResponse:
    rows = {
        row.slug: row for row in db.scalars(select(McpServer).where(McpServer.user_id == user_id))
    }
    items = []
    for entry in CATALOG:
        installed = rows.get(entry.slug)
        items.append(
            CatalogItem(
                slug=entry.slug,
                display_name=entry.display_name,
                summary=entry.summary,
                transport=entry.transport,
                tags=list(entry.tags),
                icon=entry.icon,
                requires_path=entry.requires_path,
                docs_url=entry.docs_url,
                updated=entry.updated,
                installed_id=installed.id if installed else None,
                last_status=installed.last_status if installed else None,
            )
        )
    return CatalogResponse(items=items, updated=CATALOG_UPDATED)


def list_servers(db: Session, user_id: int) -> McpServerListResponse:
    rows = db.scalars(
        select(McpServer).where(McpServer.user_id == user_id).order_by(McpServer.create_time.desc())
    )
    return McpServerListResponse(items=[_to_item(row) for row in rows])


# ---------- 写 ----------


def create_server(db: Session, user_id: int, payload: McpServerCreateRequest) -> McpServerItem:
    if db.scalar(
        select(McpServer).where(McpServer.user_id == user_id, McpServer.slug == payload.slug)
    ):
        raise BusinessError("这台服务器已经接入过了")

    entry = find_entry(payload.slug)
    try:
        if entry is not None:
            if payload.env and not crypto.is_configured():
                raise BusinessError("保存环境变量需要先配置 APP_SECRET_KEY")
            spec = entry.build_spec(path=payload.path, env=payload.env or {})
        else:
            spec = _custom_spec(payload)
    except ValueError as exc:  # CatalogEntry 的「缺 path」提示，比 spec 的通用校验更好读
        raise BusinessError(str(exc)) from exc
    except McpError as exc:
        raise BusinessError(str(exc)) from exc

    row = McpServer(
        user_id=user_id,
        slug=spec.slug,
        display_name=spec.display_name,
        transport=spec.transport,
        command=spec.command,
        args=list(spec.args),
        url=spec.url,
        env_ciphertext=_encrypt_env(payload.env),
        enabled=True,
        last_status=STATUS_UNKNOWN,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_item(row)


def _custom_spec(payload: McpServerCreateRequest) -> McpServerSpec:
    """自定义条目：字段必须齐全，再交给同一套校验。"""
    if not payload.transport:
        raise BusinessError("自定义条目要指定 transport（stdio 或 http）")
    if not payload.display_name:
        raise BusinessError("自定义条目要给一个显示名")
    if payload.transport == "stdio" and not payload.command:
        raise BusinessError("stdio 条目要指定启动命令")
    if payload.transport == "http" and not payload.url:
        raise BusinessError("http 条目要指定服务器 URL")
    return McpServerSpec(
        slug=payload.slug,
        display_name=payload.display_name,
        transport=payload.transport,
        command=payload.command,
        args=tuple(payload.args or ()),
        url=payload.url,
        env=dict(payload.env or {}),
    )


def update_server(
    db: Session, user_id: int, server_id: int, payload: McpServerUpdateRequest
) -> McpServerItem:
    row = _get_row(db, user_id, server_id)
    changes: dict[str, Any] = {}
    if payload.display_name is not None:
        changes["display_name"] = payload.display_name
    if payload.args is not None:
        changes["args"] = tuple(payload.args)
    if payload.url is not None:
        changes["url"] = payload.url

    # 用改后的值重建 spec 做校验：只改了 args 也要保证整体仍然合法
    try:
        candidate = McpServerSpec(**{**row.spec_payload, **changes}, env=_decrypt_env_safe(row))
    except McpError as exc:
        raise BusinessError(str(exc)) from exc

    row.display_name = candidate.display_name
    row.args = list(candidate.args)
    row.url = candidate.url
    if payload.env is not None:
        row.env_ciphertext = _encrypt_env(payload.env)
    if payload.enabled is not None:
        row.enabled = payload.enabled

    db.commit()
    db.refresh(row)
    # 配置变了：丢掉旧连接，否则下次 run 连的还是老进程
    get_manager().forget(row.id)
    return _to_item(row)


def delete_server(db: Session, user_id: int, server_id: int) -> None:
    row = _get_row(db, user_id, server_id)
    get_manager().forget(row.id)
    db.delete(row)
    db.commit()


def test_server(db: Session, user_id: int, server_id: int) -> McpTestResponse:
    row = _get_row(db, user_id, server_id)
    started = time.perf_counter()
    ok, message, tools = probe(spec_of_row(row))
    duration = int((time.perf_counter() - started) * 1000)

    row.last_status = STATUS_OK if ok else STATUS_ERROR
    row.last_error = None if ok else message[:255]
    row.tool_count = len(tools)
    if ok:
        row.last_connected_time = datetime.now()  # noqa: DTZ005
    db.commit()

    return McpTestResponse(
        ok=ok,
        message=message,
        tools=_briefs(tools, slug=row.slug),
        duration_ms=duration,
    )


__all__ = [
    "create_server",
    "delete_server",
    "list_catalog",
    "list_servers",
    "spec_of_row",
    "test_server",
    "update_server",
]
