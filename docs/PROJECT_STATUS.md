# 项目状态

> 一页纸：**现在在哪、下一步做什么、有什么坑**。每次任务开始前读它，结束后更新它（AGENTS.md §7）。
> 最近更新：2026-11-07 · 工作区干净 · `main` 与 `origin/main` 同步（`c219c74`，文档治理 5 个提交已推送）

## 1. 现在在哪

**按 [`playbooks/05-development-plan-and-mvp-tasks.md`](playbooks/05-development-plan-and-mvp-tasks.md) 的 11 阶段计划：阶段 1–3 已完成，阶段 4「LLM 接入与基础对话」待开工。**

阶段口径只以该文件为准。此前本文件里出现的「阶段 2 = MCP client / Agent PoC / Electron 骨架」是我自行归纳的临时说法（源自 `archive/REUSE_CANDIDATES.md` 的「MCP 建议尽早」与 ADR-0001 的 Electron 结论），**与 11 阶段计划无对应关系，已废弃**，勿再引用。

已经有一个能跑、能测、能部署的最小闭环：

- 后端 FastAPI（11 个业务接口 + 3 个运维路径，商品 + 分类 CRUD + 统计）
- 前端 Vue 3 管理后台（3 个页面 + 3 个弹窗，18 项端到端验收全过）
- 数据库迁移（Alembic）、依赖锁定（uv / pnpm）、质量门禁（ruff / ESLint / pytest / Vitest / CI）、容器化（Docker Compose）

## 2. 已完成

| 日期 | 交付 | 证据 |
|---|---|---|
| 11-07 | **名称空白校验统一**：分类改名、商品改名与新增同规则（先 strip 再判空，纯空白 400），补 5 个用例 | T-22 已解决、[api.md](api.md) §2.5/§3.3 |
| 11-07 | **文档治理四批 + 终检**：39 份文档全量审查（22 条事实陈旧、11 处职责重叠、6 处缺失），四批重构 + [终检报告](DOCUMENTATION_FINAL_REPORT.md)；人读 1348 行 / AI 向 1739 行 / 归档 672 行，0 孤儿 0 失效链接 | [审查报告](DOCUMENTATION_AUDIT.md)、[重构方案](DOCUMENTATION_REFACTOR_PLAN.md) |
| 11-07 | **测试基线**：后端 55 例 + 覆盖率门槛 80%（实测 85.38%），前端 Vitest 17 例 | [ADR-0005](adr/0005-testing-baseline.md) |
| 11-07 | **容器化**：多阶段镜像 + Compose（db/backend/frontend/可选 Caddy）+ `/healthz` `/readyz` | [ADR-0004](adr/0004-deployment-docker-compose.md)、[deploy.md](deploy.md) |
| 11-07 | **uv 统一依赖**：`pyproject.toml` 唯一来源 + `uv.lock`，CI 用 `uv sync --frozen` | `a09763d` |
| 11-07 | **前端轻量门禁**：ESLint 10 + Prettier + CI 前端 job | [ADR-0002](adr/0002-frontend-quality-gate-lite.md) |
| 11-07 | **Alembic 接管 schema**：首个 revision `2a89b3237f54` | [ADR-0003](adr/0003-database-migrations-alembic.md) |
| 11-06 | **商品管理网站 v1**：需求 → 设计 → 前后端 → 18 项验收 | [delivery.md](delivery.md) |
| 11-05 | 后端工程化：ruff / pytest / pre-commit / CI / Makefile | `python/fastapi-demo/README.md` |

## 3. 下一步

### 3.1 阶段对照表（严格按 11 阶段计划）

| # | 阶段 | 状态 | 证据 / 缺口 |
|---|---|---|---|
| 1 | AI 开发基建 | ✅ | `AGENTS.md`、`agents/`、`.agents/skills/`、`adr/`、`playbooks/` |
| 2 | 前后端项目骨架 | ✅ | `python/fastapi-demo/`、`fullstack/product-admin/` |
| 3 | 基础 API 和数据库 | ✅ | 11 个业务接口、Alembic 迁移、MySQL |
| 4 | **LLM 接入与基础对话** | ⏳ 下一阶段 | 见 §3.2 |
| 5 | Agent 基础执行循环 | ⬜ | 依赖 4 |
| 6 | Tool Calling | ⬜ | 依赖 5 |
| 7 | Skill 和 MCP | ⬜ | 依赖 6；MCP client 在此阶段做（不自造协议，用官方 SDK） |
| 8 | RAG 和 Memory | ⬜ | 依赖 7 |
| 9 | Agent 应用功能完善 | ⬜ | 依赖 8 |
| 10 | 桌面端集成 | ⬜ | 按 [ADR-0001](adr/0001-desktop-shell-electron.md)（Electron + PyInstaller onedir） |
| 11 | 部署、测试和发布 | ⚠️ 部分 | 容器化 ✅、测试基线 ✅、CI ✅；**发布流程（版本号/镜像归档/回滚）未做** |

### 3.2 阶段 4 的接入方式（已定，设计见 [`chat.md`](chat.md)）

1. **先 C 打底**：定义 `LLMClient` 协议 + 一个返回固定文本的 `FakeLLM`，在没有 API key 的情况下把「请求 → 流式输出 → 错误处理 → 测试」整条链路立起来，可独立验证。
2. **随后接 A**：用 OpenAI 兼容 API（`base_url` + `api_key`，走 `.env`），把 `FakeLLM` 换成真实现，其余代码不动。

不做 B（本地 Ollama）作为主线：需要拉数 GB 模型，且与「应用层 Agent」目标无关；如后续要离线演示再作为可选实现接入。

### 3.3 进入阶段 4 前要满足的门槛

| 门槛 | 判定标准 | 现状 |
|---|---|---|
| 文档可信 | `docs/` 无已知过期事实 | ✅ 2026-11-07（见 [DOCUMENTATION_FINAL_REPORT.md](DOCUMENTATION_FINAL_REPORT.md) §3） |
| 基线可跑 | `make check` 55 passed / ≥80%、`pnpm lint && pnpm test && pnpm build` 全过 | ✅ 2026-11-07 |
| 存储明确 | 对话数据存哪（新表 or 不落库）、是否需要会话 ID | 待定，阶段 4 设计阶段一并决定 |

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
