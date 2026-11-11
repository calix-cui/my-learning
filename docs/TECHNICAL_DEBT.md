# TECHNICAL_DEBT — 还没处理的问题

> 只记**当前仍然存在**的问题。已解决的不要留在这里，去 git 历史或 ADR 里查。
> 最近校准：2026-11-11（阶段 6 完成后）· 上一版是 2026-11-06 的全量调研，已按现状重写。
> 评级：**P0** 会反复咬人 / **P1** 该尽快做 / **P2** 排期再说。成本：**S** < 半天 / **M** 1–2 天 / **L** > 2 天。
> 每条都给证据位置；推断未验证的会标「待验证」。

## 0. 汇总

| ID | 类别 | 问题 | 优先级 | 成本 |
|---|---|---|---|---|
| T-04 | 后端 | 测试跑在 SQLite 上，MySQL 方言（JSON 默认值、索引长度、`ON DELETE`）没被 CI 覆盖 | P1 | M |
| T-06 | 后端 | `Response.data: Any` —— OpenAPI 看不到真实结构，前端只能看文档 | P1 | M |
| T-11 | 验收 | E2E 脚本直接打本地开发库（会真的注册账号、写会话），只能靠事后清理 | P1 | M |
| T-17 | 后端 | CORS 白名单写死 localhost:5173/4173，`allow_methods=["*"]`；换域名要改代码 | P1 | S |
| T-21 | 前端 | Element Plus 打成一个 ~920KB chunk，首屏为它付全价 | P2 | M |
| T-23 | 后端 | 没有统一日志与 request id，排障只能看 uvicorn 默认输出 | P2 | M |
| T-15 | 后端 | 会话列表 `total` 与 `items` 两次独立查询，并发下可能不一致 | P2 | S |
| T-18 | 数据 | `create_time` 用 naive `datetime.now`，没有时区语义（容器 UTC / 本机 CST 混用） | P2 | S |
| T-26 | Agent | `ToolMeta.timeout_seconds` 声明了但没人用，`_execute()` 固定用 `TOOL_TIMEOUT_SECONDS = 2.0` | P2 | S |
| T-27 | 前端 | `styles/index.css` 的兜底 token 与 `theme/themes/pine.ts` 有细微不一致（success/warn），靠人工同步 | P2 | S |

已随模块归档或已在实现中解决的条目（T-01/02/03/05/07/09/12/13/14/16/19/20/22/24/25）不再列出。

## 1. 后端与数据

### T-04 MySQL 方言没有测试覆盖（P1 · M）
- **证据**：`backend/tests/conftest.py` 的 `db_session` 用内存 SQLite；`app/models/*.py` 里的 `server_default=text("('[]')")`、`JSON` 列、`utf8mb4` 索引长度只有真 MySQL 才验得到。
- **咬人方式**：阶段 6 加 `agent_approvals` 迁移时就踩过——SQLite 建表通过，MySQL 上 `JSON` 默认值要写成 `('[]')`，`drop_index` 还会因为外键报 1553。
- **建议**：CI 加一个 MySQL service 的 job 只跑 `alembic upgrade head` + `alembic check`（不跑全量测试），把方言问题挡在合并前。参考 `.github/workflows/ci.yml` 现有两个 job 的写法。

### T-06 `Response.data: Any`（P1 · M）
- **证据**：`backend/app/common/response.py:12` `data: Any = None`；每个接口的真实结构只写在 `docs/api.md`。
- **代价**：`/docs` 上所有响应的 `data` 都是空对象，前端联调只能读文档；也没法从 OpenAPI 生成类型。
- **建议**：给 `Response` 加泛型（`Response[ConversationResponse]`）或按接口声明 `response_model=Envelope[Item]`。改造面大，建议和「前端生成 client」一起做。

### T-15 列表 total 与 items 不同源（P2 · S）
- **证据**：`backend/app/services/chat_service.py:44` 先算 `total`，随后另起一条查询取 `items`。
- **影响**：并发增删时会出现「total=11 但只返回 10 条」这类偏差，分页器会多出一页空页。
- **建议**：要么接受（前端容忍），要么用窗口函数 `count(*) over()` 一次查完。

### T-18 naive datetime（P2 · S）
- **证据**：`backend/app/models/conversation.py:35`、`agent_run.py:63`、`agent_step.py:64`、`agent_approval.py:69` 都是 `default=datetime.now`。
- **影响**：容器里是 UTC，本机是 CST，导出的 JSON 时间会差 8 小时且没有偏移量标注。
- **建议**：统一 `datetime.now(UTC)` + 序列化时带 `+00:00`；存量数据需要一次迁移（可以只标注「按本机时区解释」）。

### T-17 CORS 写死（P1 · S）
- **证据**：`backend/app/main.py:28-41`，`ALLOWED_ORIGINS` 是硬编码列表，`allow_methods=["*"]`。
- **影响**：换部署域名必须改代码重新发版；`allow_methods` 全开也放大了预检面。
- **建议**：改成 `settings.cors_origins`（逗号分隔的环境变量），生产默认空（靠同域反代），显式列出方法。

### T-23 没有统一日志（P2 · M）
- **证据**：`backend/app/main.py` 与 `config.py` 里没有 `logging` 配置；排障依赖 uvicorn 默认输出与 `print`。
- **缺失**：request id、耗时、用户 id、SSE 断流原因都进不了日志。
- **建议**：`logging.config.dictConfig` + 中间件生成 `request_id`（响应头回传），把 `app/api/__init__.py` 的异常处理器接进来。

## 2. Agent 与工具

### T-26 工具超时声明未生效（P2 · S）
- **证据**：`backend/app/agent/tools/base.py` 的 `ToolMeta.timeout_seconds=2.0` 只是元数据；`backend/app/agent/executor.py` 的 `_execute()` 用模块常量 `TOOL_TIMEOUT_SECONDS = 2.0`。
- **影响**：将来某个工具想声明更长/更短超时（比如 MCP 远程工具要 10s），改了 meta 也不会生效，是个静默陷阱。
- **建议**：`_execute()` 改成读 `meta_of(tool).timeout_seconds`，MCP 来源再单独放宽上限。

## 3. 前端

### T-21 Element Plus 单 chunk 偏大（P2 · M）
- **证据**：`pnpm build` 产物 `dist/assets/element-*.js` 约 920KB（gzip 前），`ChatView-*` 约 140KB。
- **影响**：首屏要下完整个组件库才能交互，弱网下白屏时间明显。
- **建议**：按需引入（`unplugin-vue-components` + ElementPlusResolver）或把设置/弹窗类组件改成 `defineAsyncComponent` 懒加载。

### T-27 兜底 token 与主题文件不同步（P2 · S）
- **证据**：`frontend/src/styles/index.css:20-26` 的 `:root` 兜底值手抄自 `frontend/src/theme/themes/pine.ts`，两边的 `success` / `warn` 已经对不上（`#2f6b52` vs `#1a7f63`、`#b4722a` vs `#a3651f`）。
- **影响**：JS 装上主题之前的第一帧颜色会和最终主题不一致；改主题时容易漏改一边。
- **建议**：兜底值只保留 `canvas/surface/ink/muted` 这几个「防闪白」必需的，其余交给运行时；或在应用启动时由 `apply.ts` 立即覆盖并加单测断言两边一致。

## 4. 验收与环境

### T-11 E2E 打真实开发库（P1 · M）
- **证据**：`frontend/scripts/*-acceptance.mjs` 全都直接请求 `http://127.0.0.1:8000`，注册 `*-e2e-<时间戳>@example.com` 账号并写真实会话/run。
- **影响**：跑几轮验收就堆几十个垃圾账号（曾累到 112 个）；如果有人拿本地库当"重要数据"，跑验收就是污染。
- **现状缓解**：`make clean-demo`（`backend/scripts/cleanup_demo_accounts.py`）可以按 `@example.com` 一次性清掉，并打印级联删除数量。
- **根治建议**：E2E 起一个独立库（`my_agent_e2e`，compose profile 或 `DATABASE_URL` 覆盖），跑完 drop。

## 5. 卫生

- 工作区里 `frontend/dist/`、`backend/.ruff_cache/`、`__pycache__/`、`.DS_Store` 都会被 `.gitignore` 挡住，但会一直留在磁盘上；已经清过一次，不必每次纠结。
