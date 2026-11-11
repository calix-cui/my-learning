"""同步桥：在一个独立线程里跑事件循环，把 async 的 MCP 调用变成同步调用。

为什么要这一层：执行器（`app/agent/executor.py`）是同步生成器，SSE 是同步输出；
而 MCP SDK 全是 async。与其把整条链路改成 async（影响面大、还要重写测试），
不如把 async 关在一个线程里——连接对象也只在这个线程的循环里被触碰，天然无锁。
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

from app.mcp.errors import McpError, McpErrorKind

T = TypeVar("T")

DEFAULT_SUBMIT_TIMEOUT = 15.0


class AsyncRunner:
    """持有「一个线程 + 一个事件循环」，生命周期与应用一致。

    用法：

    ```python
    runner = AsyncRunner()
    client = runner.submit(McpClient.connect(spec))
    tools = runner.submit(client.list_tools())
    runner.submit(client.aclose())
    runner.close()
    ```
    """

    def __init__(self, name: str = "mcp-runner") -> None:
        self._name = name
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._closed = False

    def submit(self, coro: Coroutine[Any, Any, T], *, timeout: float = DEFAULT_SUBMIT_TIMEOUT) -> T:
        """在后台循环里执行协程并等结果。"""
        loop = self._ensure_loop()
        if self._closed:
            coro.close()
            raise McpError(McpErrorKind.CONNECT, "MCP 运行时已关闭")

        future: Any = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as exc:
            future.cancel()
            raise McpError(McpErrorKind.TIMEOUT, "MCP 调用超时", detail="runner") from exc

    def close(self) -> None:
        """停循环、收线程。可重复调用。"""
        if self._closed:
            return
        self._closed = True
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._loop = None
        self._thread = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None:
            return self._loop

        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        if self._loop is None:  # pragma: no cover - 线程起不来属于环境问题
            raise McpError(McpErrorKind.CONNECT, "MCP 运行时启动失败", detail="event loop")
        return self._loop

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
