"""MCP 客户端：把 SDK 的 async 连接关进一个「监督协程」里，对外全是同步方法。

为什么不直接在每个方法里开 async with：anyio 的 cancel scope 要求**进出一致**，
即进入 scope 的任务必须负责退出。若「连接」由一个任务建立、「关闭」由另一个任务执行，
SDK 会抛 `RuntimeError: Attempted to exit cancel scope in a different task`。

所以这里的形状是：
- 一个监督协程（在 `AsyncRunner` 的循环里跑）负责 connect → 收请求 → 分发 → 关闭；
- 同步方每次调用只是往队列里塞一个请求，然后等它的 future。

对外只有五个同步方法：`connect` / `list_tools` / `call_tool` / `close` / `connected`。
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation, PaginatedRequestParams, TextContent

from app.mcp.errors import McpError, McpErrorKind
from app.mcp.runner import AsyncRunner
from app.mcp.specs import McpCallResult, McpServerSpec, McpToolInfo

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_CALL_TIMEOUT = 10.0

_CLIENT_INFO = Implementation(name="my-agent", version="0.1.0")

RequestKind = Literal["list", "call"]


@dataclass
class _Request:
    kind: RequestKind
    future: asyncio.Future[Any]
    name: str | None = None
    arguments: dict[str, Any] | None = None
    timeout: float = DEFAULT_CALL_TIMEOUT


@dataclass
class _Handle:
    """在循环里创建、跨线程传递的句柄。"""

    queue: asyncio.Queue[_Request | None]
    ready: asyncio.Future[None]
    task: asyncio.Task[None] = field(repr=False, default=None)  # type: ignore[assignment]


class McpClient:
    """一条 MCP 连接（同步门面）。线程安全：所有协作都通过队列完成。"""

    def __init__(self, spec: McpServerSpec, runner: AsyncRunner) -> None:
        self.spec = spec
        self._runner = runner
        self._handle: _Handle | None = None
        self._closed = False

    # ---------- 生命周期 ----------

    def connect(self, *, timeout: float = DEFAULT_CONNECT_TIMEOUT) -> None:
        """建立连接并完成握手，失败抛 `McpError`。"""
        if self._handle is not None:
            return
        try:
            self._handle = self._runner.submit(self._bootstrap(timeout), timeout=timeout + 5.0)
        except McpError:
            raise
        except Exception as exc:  # 统一成 McpError
            raise McpError(
                McpErrorKind.CONNECT, "无法连接 MCP 服务器", detail=f"{self.spec.slug}: {exc}"
            ) from exc

    def close(self) -> None:
        """关闭连接（可重复调用）。"""
        if self._closed:
            return
        self._closed = True
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        self._runner.submit(self._shutdown(handle), timeout=10.0)

    @property
    def connected(self) -> bool:
        return self._handle is not None and not self._closed

    # ---------- 三个业务方法 ----------

    def list_tools(self, *, timeout: float = DEFAULT_CALL_TIMEOUT) -> list[McpToolInfo]:
        return self._request(_Request(kind="list", future=None, timeout=timeout))  # type: ignore[arg-type]

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: float = DEFAULT_CALL_TIMEOUT,
    ) -> McpCallResult:
        return self._request(  # type: ignore[return-value]
            _Request(kind="call", future=None, name=name, arguments=arguments, timeout=timeout)  # type: ignore[arg-type]
        )

    # ---------- 内部 ----------

    def _request(self, req: _Request) -> Any:
        if not self.connected or self._handle is None:
            raise McpError(McpErrorKind.CONNECT, "MCP 连接未建立", detail=self.spec.slug)
        try:
            return self._runner.submit(self._send(self._handle, req), timeout=req.timeout + 5.0)
        except McpError:
            raise
        except Exception as exc:
            raise McpError(
                McpErrorKind.PROTOCOL, "MCP 调用失败", detail=f"{self.spec.slug}: {exc}"
            ) from exc

    async def _send(self, handle: _Handle, req: _Request) -> Any:
        loop = asyncio.get_running_loop()
        req.future = loop.create_future()
        await handle.queue.put(req)
        return await req.future

    async def _bootstrap(self, timeout: float) -> _Handle:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[_Request | None] = asyncio.Queue()
        ready: asyncio.Future[None] = loop.create_future()
        task = loop.create_task(self._serve(queue, ready, timeout))
        handle = _Handle(queue=queue, ready=ready, task=task)
        await ready
        return handle

    async def _shutdown(self, handle: _Handle) -> None:
        await handle.queue.put(None)
        try:
            await asyncio.wait_for(handle.task, timeout=8.0)
        except (TimeoutError, asyncio.CancelledError):
            handle.task.cancel()

    async def _serve(
        self,
        queue: asyncio.Queue[_Request | None],
        ready: asyncio.Future[None],
        connect_timeout: float,
    ) -> None:
        """监督协程：唯一进入/退出 SDK scope 的任务。"""
        try:
            async with AsyncExitStack() as stack:
                read, write = await self._open(stack)
                session = await stack.enter_async_context(
                    ClientSession(read, write, client_info=_CLIENT_INFO)
                )
                await asyncio.wait_for(session.initialize(), timeout=connect_timeout)
                ready.set_result(None)
                await self._pump(queue, session)
        except Exception as exc:
            if not ready.done():
                ready.set_exception(_translate(exc, self.spec))
                return
            raise

    async def _pump(self, queue: asyncio.Queue[_Request | None], session: ClientSession) -> None:
        while True:
            req = await queue.get()
            if req is None:
                return
            try:
                if req.kind == "list":
                    req.future.set_result(await self._do_list(session, req.timeout))
                else:
                    req.future.set_result(
                        await self._do_call(session, req.name or "", req.arguments, req.timeout)
                    )
            except Exception as exc:  # 单次调用失败不该断开连接
                if not req.future.done():
                    req.future.set_exception(_translate(exc, self.spec))

    async def _open(self, stack: AsyncExitStack) -> tuple[Any, Any]:
        if self.spec.is_stdio:
            # 继承父进程环境再叠加自定义变量：npx/uvx 要靠 PATH/HOME 才能跑起来。
            params = StdioServerParameters(
                command=self.spec.command or "",
                args=list(self.spec.args),
                env={**os.environ, **self.spec.env},
            )
            return await stack.enter_async_context(stdio_client(params))
        return await stack.enter_async_context(streamable_http_client(self.spec.url or ""))

    async def _do_list(self, session: ClientSession, timeout: float) -> list[McpToolInfo]:
        tools: list[McpToolInfo] = []
        cursor: str | None = None
        while True:
            params = PaginatedRequestParams(cursor=cursor) if cursor else None
            page = await asyncio.wait_for(session.list_tools(params=params), timeout)
            tools.extend(_to_tool_info(tool) for tool in page.tools)
            cursor = page.next_cursor
            if not cursor:
                return tools

    async def _do_call(
        self,
        session: ClientSession,
        name: str,
        arguments: dict[str, Any] | None,
        timeout: float,
    ) -> McpCallResult:
        result = await asyncio.wait_for(session.call_tool(name, arguments or {}), timeout)
        blocks = [_block_to_dict(block) for block in result.content]
        text = "\n".join(b["text"] for b in blocks if b["type"] == "text").strip()
        if not text:
            text = json.dumps(blocks, ensure_ascii=False)
        return McpCallResult(ok=not result.is_error, text=text, raw=blocks)


def _translate(exc: BaseException, spec: McpServerSpec) -> McpError:
    """把 SDK / 系统异常翻译成 `McpError`。"""
    if isinstance(exc, McpError):
        return exc
    if isinstance(exc, TimeoutError):
        return McpError(McpErrorKind.TIMEOUT, "MCP 调用超时", detail=spec.slug)
    if isinstance(exc, FileNotFoundError):
        return McpError(McpErrorKind.CONNECT, f"启动命令不存在：{spec.command}", detail=spec.slug)
    return McpError(McpErrorKind.CONNECT, "无法连接 MCP 服务器", detail=f"{spec.slug}: {exc}")


def _to_tool_info(tool: Any) -> McpToolInfo:
    annotations = tool.annotations
    read_only = bool(getattr(annotations, "read_only_hint", False)) if annotations else False
    return McpToolInfo(
        name=tool.name,
        description=tool.description or "",
        input_schema=dict(tool.input_schema or {}),
        read_only=read_only,
    )


def _block_to_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, TextContent):
        return {"type": "text", "text": block.text}
    payload = block.model_dump(mode="json", exclude_none=True)
    return {"type": str(payload.get("type", "unknown")), **payload}
