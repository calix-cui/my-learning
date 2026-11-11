"""连接管理：一个进程内最多对每台 server 保持一条连接。

为什么需要它：装配注册表发生在**每次 run 开始**，而 stdio server 启动要拉起子进程
（`uvx`/`npx` 往往 1–3 秒）。若每次 run 都重连，第一句话就会卡住；若永久缓存，
用户在设置页改了参数却连的还是老进程。折中：按行缓存连接，工具清单 5 分钟刷新一次，
连接空闲 15 分钟回收。

并发：`McpClient` 的调用都经过同一个 supervisor 协程串行处理，所以多个工具同时被
调用时不会踩到 SDK；多个 server 之间互不影响（各自一条连接）。
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.mcp.client import McpClient
from app.mcp.errors import McpError
from app.mcp.runner import AsyncRunner
from app.mcp.source import McpSource
from app.mcp.specs import McpServerSpec, McpToolInfo

if TYPE_CHECKING:
    from app.models.mcp_server import McpServer

logger = logging.getLogger(__name__)

TOOL_CACHE_SECONDS = 300.0
IDLE_SECONDS = 900.0


@dataclass
class _Connection:
    client: McpClient
    tools: list[McpToolInfo] = field(default_factory=list)
    tools_at: float = 0.0
    used_at: float = 0.0

    def stale(self, now: float) -> bool:
        return not self.tools or now - self.tools_at > TOOL_CACHE_SECONDS

    def idle(self, now: float) -> bool:
        return now - self.used_at > IDLE_SECONDS


class McpManager:
    """按 `mcp_servers.id` 缓存连接。测试里可以自己 new 一个，避免串到全局状态。"""

    def __init__(self, *, runner: AsyncRunner | None = None) -> None:
        self._runner = runner or AsyncRunner(name="mcp-manager")
        self._connections: dict[int, _Connection] = {}
        self._lock = threading.RLock()

    # ---------- 对外 ----------

    def source_for(self, server: McpServer, *, env: dict[str, str] | None = None) -> McpSource:
        """取（必要时建立）这台 server 的 source。失败抛 `McpError`。"""
        spec = McpServerSpec(**server.spec_payload, env=env or {})
        with self._lock:
            conn = self._connections.get(server.id or -1)
            now = time.monotonic()

            if conn is not None and not conn.client.connected:
                conn = None
            if conn is None:
                conn = _Connection(client=McpClient(spec, self._runner))
                conn.client.connect()
                self._connections[server.id or -1] = conn

            if conn.stale(now):
                try:
                    conn.tools = conn.client.list_tools()
                    conn.tools_at = now
                except McpError:
                    # 列工具失败说明连接已坏：丢掉，下次重连（不要留半死连接）
                    self._drop(server.id or -1)
                    raise

            conn.used_at = now
            return McpSource(
                conn.client,
                slug=spec.slug,
                server_name=spec.display_name,
                tools=list(conn.tools),
            )

    def forget(self, server_id: int) -> None:
        """用户删除/修改了某台 server：关掉并丢弃它的连接。"""
        with self._lock:
            self._drop(server_id)

    def close_all(self) -> None:
        with self._lock:
            for server_id in list(self._connections):
                self._drop(server_id)

    def sweep(self, *, now: float | None = None) -> int:
        """回收空闲连接，返回关掉几个。由清理任务或设置页刷新时顺带调用。"""
        moment = time.monotonic() if now is None else now
        with self._lock:
            stale_ids = [sid for sid, conn in self._connections.items() if conn.idle(moment)]
            for server_id in stale_ids:
                self._drop(server_id)
            return len(stale_ids)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"connections": len(self._connections)}

    # ---------- 内部 ----------

    def _drop(self, server_id: int) -> None:
        conn = self._connections.pop(server_id, None)
        if conn is None:
            return
        try:
            conn.client.close()
        except Exception:  # pragma: no cover - 关闭失败不该影响主流程
            logger.warning("关闭 MCP 连接失败：%s", server_id, exc_info=True)


_manager: McpManager | None = None
_manager_lock = threading.Lock()


def get_manager() -> McpManager:
    """进程级单例：连接要跨请求复用，不能每个请求新建。"""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = McpManager()
        return _manager


def reset_manager() -> None:
    """测试用：丢掉单例并关闭连接。"""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.close_all()
        _manager = None


def probe(spec: McpServerSpec) -> tuple[bool, str, list[McpToolInfo]]:
    """「测试连接」用：连一次、列一次、立刻关掉，不进缓存。"""
    runner = AsyncRunner(name="mcp-probe")
    client = McpClient(spec, runner)
    try:
        client.connect()
        tools = client.list_tools()
    except McpError as exc:
        return False, str(exc), []
    finally:
        try:
            client.close()
        finally:
            runner.close()
    if not tools:
        return True, "连接成功，但这台服务器没有暴露任何工具", []
    return True, f"连接成功，发现 {len(tools)} 个工具", tools


__all__ = [
    "IDLE_SECONDS",
    "TOOL_CACHE_SECONDS",
    "McpManager",
    "get_manager",
    "probe",
    "reset_manager",
]
