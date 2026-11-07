# 项目状态

> 一页纸：**现在在哪、下一步做什么、有什么坑**。每次任务开始前读它，结束后更新它（AGENTS.md §7）。
> 最近更新：2026-11-07 · 工作区干净 · `main` 与 `origin/main` 同步

## 1. 现在在哪

**阶段 1「工程基建」已完成，准备进入阶段 2「架构与 Agent 能力设计」。**

已经有一个能跑、能测、能部署的最小闭环：

- 后端 FastAPI（11 个业务接口 + 3 个运维路径，商品 + 分类 CRUD + 统计）
- 前端 Vue 3 管理后台（3 个页面 + 3 个弹窗，18 项端到端验收全过）
- 数据库迁移（Alembic）、依赖锁定（uv / pnpm）、质量门禁（ruff / ESLint / pytest / Vitest / CI）、容器化（Docker Compose）

## 2. 已完成

| 日期 | 交付 | 证据 |
|---|---|---|
| 11-07 | **名称空白校验统一**：分类改名、商品改名与新增同规则（先 strip 再判空，纯空白 400），补 5 个用例 | T-22 已解决、[api.md](../python/fastapi-demo/docs/api.md) §2.5/§3.3 |
| 11-07 | **文档体系重构**：三层结构 + 架构图/工具链图，人读部分从 2900 行降到 1350 行，重复事实收敛到单一来源 | [docs/README.md](README.md)、[CONTRIBUTING.md](../CONTRIBUTING.md) |
| 11-07 | **测试基线**：后端 55 例 + 覆盖率门槛 80%（实测 85.38%），前端 Vitest 17 例 | [ADR-0005](adr/0005-testing-baseline.md) |
| 11-07 | **容器化**：多阶段镜像 + Compose（db/backend/frontend/可选 Caddy）+ `/healthz` `/readyz` | [ADR-0004](adr/0004-deployment-docker-compose.md)、[deploy.md](deploy.md) |
| 11-07 | **uv 统一依赖**：`pyproject.toml` 唯一来源 + `uv.lock`，CI 用 `uv sync --frozen` | `a09763d` |
| 11-07 | **前端轻量门禁**：ESLint 10 + Prettier + CI 前端 job | [ADR-0002](adr/0002-frontend-quality-gate-lite.md) |
| 11-07 | **Alembic 接管 schema**：首个 revision `2a89b3237f54` | [ADR-0003](adr/0003-database-migrations-alembic.md) |
| 11-06 | **商品管理网站 v1**：需求 → 设计 → 前后端 → 18 项验收 | [delivery.md](delivery.md) |
| 11-05 | 后端工程化：ruff / pytest / pre-commit / CI / Makefile | `python/fastapi-demo/README.md` |

## 3. 下一步

**阶段 2「架构与 Agent 能力」尚未开工**。进入前先满足 3 个门槛（缺哪个先补哪个，不并行铺开）：

| 门槛 | 判定标准 | 现状 |
|---|---|---|
| 文档可信 | `docs/` 无已知过期事实 | 本轮治理后达成（见 `DOCUMENTATION_FINAL_REPORT.md`） |
| 基线可跑 | `make check` 55 passed / ≥80%、`pnpm lint && pnpm test && pnpm build` 全过、容器三容器 healthy | ✅ 2026-11-07 |
| 范围明确 | 阶段 2 只做「MCP client + 单 Agent PoC + Electron 骨架」，不做 RAG / 多 Agent | 待确认 |

阶段 2 建议顺序（每步一个可独立验证的交付，先出 ADR 再动代码）：

1. **MCP client 最小闭环** —— 能连一个 MCP server、调一个 tool、打印结果；独立于现有 API，不侵入业务代码
2. **Agent 骨架 PoC** —— OpenAI Agents SDK 与 LangGraph 二选一（先写选型 ADR），单 Agent + 1 个工具 + 1 轮对话
3. **Electron 桌面壳** —— 按 [ADR-0001](adr/0001-desktop-shell-electron.md) 起骨架，主进程 spawn 后端
4. **文档与测试跟随** —— 每步补 ADR + 用例，并把结论写回本页

剩余技术债见 [`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md)：P0/P1 已清空，剩下以 P2 为主（日志规范 T-23、Element Plus 体积 T-21）。

## 4. 关键决策

完整理由见 [`adr/`](adr/README.md)，这里只列「选了 A 不选 B」的结论：

| 决策 | 选择 | 一句话理由 |
|---|---|---|
| 后端框架 | FastAPI + SQLAlchemy 2.0 + MySQL | 类型友好、OpenAPI 自动生成 |
| 后端分层 | api / schemas / services / models / common | 控制器不写 SQL，业务可单测 |
| 前端 | Vue 3 + TS + Vite + Element Plus | 与设计稿还原度高、组件齐 |
| 通信 | REST + 统一响应 `{code,message,data}` | 简单，任意客户端可消费 |
| 数据库迁移 | Alembic | 结构变更要能复现与回滚（ADR-0003） |
| 依赖管理 | uv（后端）+ pnpm（前端） | 锁定完整依赖树，CI 可复现 |
| 质量门禁 | 后端严（ruff+pytest+80% 覆盖）、前端轻（ESLint recommended + Vitest 纯逻辑） | 单人项目，摩擦要小于收益（ADR-0002） |
| 部署 | Docker Compose（db/backend/frontend/可选 Caddy） | 一条命令起全套（ADR-0004） |
| 桌面端外壳 | Electron + PyInstaller `--onedir` | 复用 Node 工具链，拉起本地后端最省事（ADR-0001） |
| Agent 框架 | **未决策**（MCP Python SDK 先 client，OpenAI Agents SDK 先 PoC） | 需求未定，先走最小可验证路径 |

## 5. 已知问题

按优先级见 [`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md)（T-01…T-25）。当前最该处理的五条：

1. **T-04 部分解决** — 后端测试用内存 SQLite，MySQL 专有行为（唯一键 1062、外键、排序）无自动化覆盖
2. **T-05 遗留** — CI 不校验迁移一致性（`alembic check` 需要 MySQL service）
3. **T-02 遗留** — 前端 ESLint 未启 type-aware（ADR-0002 已接受该取舍）
4. **T-23** — 后端日志无统一配置、无 request id，排障只能靠 uvicorn 默认输出
5. **L-05** — 404 文案不统一（详情/删除「商品不存在」、改商品「未找到商品」），见 [delivery.md](delivery.md) §7

## 6. 阻塞与环境限制

无硬阻塞。以下是环境级限制，会在特定任务变成阻塞：

- **Docker**：本机 CLI 无 compose 插件、daemon 默认未运行；本轮用 colima（`HOME=/tmp/home`）验证过容器化，日常部署需自行启动 Docker Desktop/colima
- **gh 凭据**：`~/.gitconfig` 已配 `gh auth git-credential`，但 token 缺 `workflow` scope 时需要设备授权（见 T-13）

## 7. 仓库状态

- 最近提交：文档体系重构（三层结构 + 架构图/工具链图/契约精简），详见 `git log --oneline -8`
- CI：最近一次 run `42372731737`（`8a3e806`）双 job 绿；只改 `docs/` 的提交不会触发 CI（`ci.yml` 的 `paths` 只含 `python/fastapi-demo/**`、`fullstack/product-admin/**`、自身）
- 文档：人读 1350 行 / AI 向 1670 行 / 归档 670 行；全仓相对链接 0 失效（`/tmp/linkcheck.py` 口径）
- 测试基线：后端 55 passed / 85.38%；前端 17 passed
- 容器验证：三容器 healthy，`http://localhost:8080` 首页、`/api/products`、`/healthz`、`/readyz` 均 200；`down && up -d` 后数据仍在
