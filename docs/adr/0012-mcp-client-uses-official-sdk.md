# ADR-0012 用官方 MCP SDK 做客户端

> **AI 向文档**：本文是给 AI 协作者的决策记录。人读入口见 [`docs/README.md`](README.md)。

- **状态**：已确认（2026-11-11）
- **日期**：2026-11-11
- **相关**：[ADR-0011](0011-tool-permissions-and-approvals.md)（工具权限与审批）、[`docs/mcp.md`](../mcp.md)（阶段 7 设计）

## 背景

阶段 7 要让用户接入 MCP server。客户端只要三条方法：`initialize` 握手、`tools/list` 列工具、`tools/call` 调工具。两条路线：

1. **官方 SDK** `mcp==2.3.0`：一次覆盖 stdio / streamable-http / sse 三种传输与全部协议细节；
2. **自己写最小客户端**：`httpx` + `subprocess`，约 250 行，零新增依赖。

## 决策

采用 **① 官方 `mcp==2.3.0`**。用户确认时给的理由是「协议细节交给上游，省下来的时间用在权限与页面上」。

落地约束（把 SDK 关进笼子，别让它扩散到业务层）：

1. **适配层只有一个目录**：`backend/app/mcp/`。`agent/` 仍然只认阶段 6 的 `ToolSource` 协议，不认识 SDK。
2. **只暴露三条方法**：`connect()` / `list_tools()` / `call_tool()`。`resources`、`prompts`、`sampling`、`roots`、`elicitation`、auth 协商一律不用（传 `None` 回调）。
3. **同步桥**：SDK 是 async，而执行器是同步生成器 → `runner.py` 用「独立线程 + 独立事件循环」做 `submit(coro) -> result`，MCP 连接只是在这个循环里挂着的对象，业务代码全部同步。
4. **版本钉子**：`mcp==2.3.0` 精确锁定（本仓库依赖一律精确版本），升级时跑 `tests/test_mcp_client.py` 的协议一致性用例。
5. **传输范围**：stdio 与 streamable-http。旧版 HTTP+SSE（`mcp.client.sse`）不接。

## 代价

- 新增 13 个包（`mcp` `mcp-types` `httpx2` `httpcore2` `jsonschema` `jsonschema-specifications` `referencing` `rpds-py` `opentelemetry-api` `pyjwt` `sse-starlette` `truststore` `attrs`）；
- **双 HTTP 栈**：SDK 2.x 用 `httpx2`，我们的 LLM 客户端用 `httpx` 0.28。两者并存，排查网络问题时先确认是哪一套；`mcp/specs.py` 里只允许出现 `httpx2` 的类型，业务代码不许直接 import；
- SDK 2.x 刚把 `FastMCP` 改名 `MCPServer`，API 还在动 → 升级要读 migration guide。

## 2026-11-11 追加：SDK 2.x 的两个实际坑

1. `from mcp.server.fastmcp import FastMCP` 在 2.x 直接抛 `ModuleNotFoundError`，改名后是 `from mcp.server.mcpserver import MCPServer`。
2. `mcp.client.streamable_http` 里的入口叫 `streamable_http_client`（不是 v1 的 `streamablehttp_client`），返回 `(read, write)` 二元组。

两条都写进了 `docs/mcp.md` §3.2 的「SDK 用法备忘」，避免下一个人再踩。
