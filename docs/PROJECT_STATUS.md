# PROJECT_STATUS — 项目状态

> 本文件由 AI 在每次任务开始前读取、任务结束后更新（AGENTS.md §7）。
> 最近更新：2026-11-06 · 对应提交 `4be025b`（工作区另有未提交文档）

## 1. 当前阶段

**阶段 1「Know the project」进行中**（按 `docs/prompts/` 的 7 阶段推进）。
阶段 0 的最小闭环已完成：一个可运行的 FastAPI 后端 + Vue3 管理后台 + 完整需求/设计/验收文档 + 7 个已推送的提交。

## 2. 进行中

| 任务 | 负责 | 状态 | 产出 |
|---|---|---|---|
| （无进行中任务，等待阶段 2 启动） | — | — | — |
| 项目与 AI 环境调研 | lead | 完成 | `docs/project/` 4 份：PROJECT_OVERVIEW / AI_ENVIRONMENT_AUDIT / TECHNICAL_DEBT（T-01…T-25）/ REUSE_CANDIDATES（含 Top 5） |
| 子智能体角色卡 | lead | 完成 | `docs/agents/` 5 张卡 + 协作协议 |
| 本文件初始化 | lead | 完成 | 本文件 |

## 3. 已完成（近期，倒序）

| 日期 | 交付 | 提交 |
|---|---|---|
| 11-06 | 商品管理网站 v1：PRD / 设计规范+5 张设计稿 / 后端 seed+CORS / 前端 16 文件 / 验收 18 项全过 | `7c2d6fc`…`4be025b` |
| 11-05 | 后端工程化：pyproject(ruff)/pytest 23 例/pre-commit/CI/Makefile/README | 已包含在上面的提交中 |
| 11-05 | 修复 `/api/products` 分页 500（`scalars` → `scalar`） | 同上 |
| 11-05 | 修复 VS Code 调试配置（cwd/interpreter/--reload） | `.vscode` 未入库 |
| 11-03 | `python/fastapi-demo` 模块导图与请求生命周期文档 | `docs/module-map.md`（本地） |

## 4. 阻塞

无硬阻塞。以下为**环境级限制**（会在对应阶段变成阻塞）：

- `docker` CLI 可用但 **daemon 未运行**，且无 `docker compose` 子命令 → 阶段 4 容器化前必须解决（T-24）。
- `gh` 凭据未接入 git → 每次 push 需临时绕过（T-13）。

## 5. 当前技术决策

| 决策 | 选择 | 理由 | 记录位置 |
|---|---|---|---|
| 后端框架 | FastAPI + SQLAlchemy 2.0 + MySQL | 类型友好、OpenAPI 自动生成、生态成熟 | `python/fastapi-demo/README.md` |
| 分层 | api / services / schemas / models / common | 控制器不写 SQL，业务可单测 | `docs/module-map.md` |
| 前端 | Vue3 + TS + Vite + Element Plus | 与设计稿还原度高、组件齐、团队熟悉 | `docs/design/`、`docs/product-admin/README.md` |
| 前后端通信 | REST + 统一响应 `{code,message,data}` | 简单、可被任意客户端消费 | `python/fastapi-demo/docs/api.md` |
| 质量门禁 | 后端：ruff + pytest + pre-commit + CI；前端：**轻量档**（ESLint recommended + Prettier + Vitest 仅纯逻辑） | 单人项目，门禁的摩擦要小于收益 | `pyproject.toml`、`.github/workflows/ci.yml`、[ADR-0002](adr/0002-frontend-quality-gate-lite.md) |
| 数据库迁移 | 暂用 `create_all`（**已知债务 T-05**） | 初期求快，尚未引入 Alembic | `docs/project/TECHNICAL_DEBT.md` |
| 桌面端外壳 | **Electron**（主进程 spawn Python 子进程 + electron-builder 打包） | 复用 Node 工具链、拉起本地后端最省事、调试与打包生态成熟 | [ADR-0001](adr/0001-desktop-shell-electron.md) |
| 桌面端后端打包 | **PyInstaller `--onedir`**（Nuitka 二期评估） | onefile 冷启动慢 | `docs/project/REUSE_CANDIDATES.md` §7 |
| Agent 框架 | **未决策**：MCP Python SDK（先 client）+ OpenAI Agents SDK（先 PoC） | 需求未定，先用最小可验证路径 | `docs/project/REUSE_CANDIDATES.md` §8 |
| 项目级 Skill | 按需从 GitHub 引入开源 Skill，不自研 | 成熟方案优先，见 AGENTS.md §2.1 | `docs/project/AI_ENVIRONMENT_AUDIT.md` §2 |

## 6. 已知问题

按优先级见 `docs/project/TECHNICAL_DEBT.md`（T-01…T-25）。当前最该处理的五条：

1. **T-01** `AGENTS.md` 与 `docs/prompts/` 未提交 —— 规则资产只在工作区。
2. **T-02/T-03** 前端零 lint、零单测、CI 不覆盖前端。
3. **T-04** 后端测试不连库，SQL 路径无自动化覆盖。
4. **T-05** 无迁移工具，schema 无法演进。
5. **T-12** 本机 Python 3.15 / CI 3.12，无 `.python-version`。

## 7. 下一步计划

阶段 1 已完成，owner 已确认以下顺序（2026-11-06）：

1. **Alembic 接管 schema**（P0，半天）——`stamp` 现有库 + 首个 autogenerate revision，`init_db` 改为执行迁移。
2. **前端轻量门禁**（P0，半天）——ESLint 10 flat（recommended 档）+ Prettier + CI 前端 job（`pnpm build` + `pnpm lint`），口径见 [ADR-0002](adr/0002-frontend-quality-gate-lite.md)。
3. **uv 统一依赖源**（P0，半天）——`pyproject.toml` 的 `[project.dependencies]` 成为唯一来源 + 提交 `uv.lock`，CI 用 `uv sync --frozen`。
4. **容器化与一键部署**（P1，需先解决 T-24 Docker daemon）——多阶段 Dockerfile + Compose + Caddy + `/healthz`。
5. **测试基线**（P1，半天）——后端 pytest-cov 门槛、前端 Vitest 仅纯逻辑。

后续：阶段 2 架构与 Agent 能力设计（MCP client 先行）、桌面端 Electron 骨架（按 ADR-0001）、项目级 Skill 从 GitHub 按需引入（见 AUDIT §2）。

## 8. 工作区状态（未提交）

```
?? AGENTS.md
?? docs/PROJECT_STATUS.md
?? docs/prompts/
?? docs/project/
?? docs/agents/
```

（`docs/project/`、`docs/agents/` 为本轮调研新增；`AGENTS.md`、`docs/prompts/` 为用户提供但尚未入库。）
