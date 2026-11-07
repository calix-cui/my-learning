# PROJECT_OVERVIEW — 项目现状总览

> **归档文档**：阶段性产物，不再更新。结论已并入正式文档，见 [`README.md`](README.md)。

> 调研时间：2026-11-06 · 基线提交：`4be025b`（`main`，已同步 `origin/main`）
> 本文只描述**已核实的事实**，每项结论都标注了证据文件或命令；推测性内容统一放在 `TECHNICAL_DEBT.md`。

## 1. 一句话现状

这是一个**以学习为起点、正在向「AI Agent 全栈应用」演进**的 monorepo。当前可运行的只有一套「商品管理」前后端：FastAPI + MySQL 后端（12 个接口）与 Vue 3 + Element Plus 前端（3 个页面），工程化只覆盖了后端 Python 部分；AI 开发基建（Agent/Prompt/Workflow 体系、部署、桌面打包、RAG/MCP 能力）尚未开始。

## 2. 仓库定位与所处阶段

| 维度 | 现状 |
|---|---|
| 仓库性质 | 个人学习与实践仓库，**公开仓库**（`gh repo view`：`visibility: PUBLIC`） |
| 组织方式 | Monorepo，按技术域分目录（`python/`、`frontend/`、`agent/`、`fullstack/`） |
| 当前阶段 | 阶段 0：规范先行。`AGENTS.md`（开发规范）与 `docs/prompts/1..7`（7 阶段提示词流水线）刚落地，尚未有对应产出 |
| 长期目标 | 应用层全栈 AI Agent：前后端分离、本地可跑、一键上云、可打包 macOS/Windows/Linux |
| 与本阶段的关系 | 现有 `fullstack/product-admin` 是「全栈底座验证」样本，不是最终产品 |

## 3. 目录结构（实际存在）

```text
my-learning/
├── AGENTS.md                     # AI 开发全局规范（未提交）
├── CONTRIBUTING.md               # 协作约定（README 最低要求、依赖/提交规范）
├── README.md                     # 仓库说明 + 项目索引
├── .editorconfig / .gitattributes / .gitignore
├── .pre-commit-config.yaml       # ruff + 通用文件检查（仓库根，作用于 python/fastapi-demo）
├── .github/workflows/ci.yml      # 仅覆盖 Python：ruff + pytest
├── .vscode/
│   ├── launch.json               # debugpy 调 FastAPI / 建表脚本（被 .gitignore 忽略）
│   └── settings.example.json     # 解释器、pytest、ruff 保存即格式化
├── docs/
│   ├── README.md                 # 「跨项目学习笔记」定位（已与现状不符，见技术债）
│   ├── PROJECT_STATUS.md         # 工作状态看板（本阶段新增，未提交）
│   ├── prompts/                  # 7 份分阶段 AI 提示词（1 调研 → 7 code review）
│   ├── product/                  # PRD：prd.md
│   ├── design/                   # 设计规范 234 行 + 5 份 HTML 稿 + 5 张 PNG
│   └── product-admin/            # 交付说明 + 验收报告 + 5 张实机截图
├── python/
│   └── fastapi-demo/             # 后端（独立 venv、Makefile、pyproject、tests）
└── fullstack/
    └── product-admin/            # 前端（独立 package.json、pnpm-lock、验收脚本）
```

**规划中但尚未创建**：`frontend/`、`agent/`（根 README 已列出索引小节，目录为空）。

## 4. 已有能力清单

### 4.1 后端 `python/fastapi-demo`

- 分层：`api`（路由/校验）→ `services`（业务/事务）→ `models`（ORM），`schemas` 定契约，`common` 放统一响应与异常处理器。
- 接口：7 个路径 / 12 个操作（`app.openapi()` 实测）
  `GET|POST /api/categories`、`PATCH|DELETE /api/categories/{id}`、`GET /api/categories/statistics`、`GET|POST /api/products`、`GET /api/products/count`、`GET|PATCH|DELETE /api/products/{id}`、`GET /`
- 数据模型（`app/models/`）：`categories(id, name[50] unique, create_time)`、`products(id, name[50], price Numeric(8,2), stock int, shelf_status bool, category_id FK, create_time)`，公共列由 `Base` 提供。
- 统一响应 `{code, message, data}` + 5 个全局异常处理器（业务异常 / SQLAlchemy / HTTP / 参数校验 / 兜底）。
- 分页 + 关键字模糊搜索 + 分类筛选 + 联表 + 分组统计。
- 演示数据脚本 `app/seed.py`（重置为 3 分类 / 14 商品）。
- 测试 23 个（`pytest` + `TestClient`，**不连数据库**），`0.38s` 全绿。

### 4.2 前端 `fullstack/product-admin`

- 3 个页面：商品列表（搜索/筛选/分页/增删改）、分类管理（增改删 + 商品数条）、概览（统计卡/分布条/环形图/库存预警/最近新增）。
- 技术：Vue 3.5 `<script setup>` + TS + Vite 6 + Element Plus + axios + vue-router 4；`@` 别名；`manualChunks` 拆 vue/element。
- 开发与预览都用 Vite proxy 把 `/api` 转发到 `127.0.0.1:8000`（`vite.config.ts:19-37`）。
- 端到端验收脚本 `scripts/acceptance.mjs`（puppeteer-core，18 项 UI 用例），已固化 `pnpm acceptance`。

### 4.3 文档资产

| 文档 | 作用 | 规模 |
|---|---|---|
| `docs/product/prd.md` | 16 条 P0 + 15 条验收标准 + 7 条待确认 | 399 行 |
| `docs/design/design.md` | 设计 token、组件规格、状态色语义 | 234 行 |
| `python/fastapi-demo/docs/api.md` | 接口契约（请求/响应/错误码） | 919 行 |
| `docs/delivery.md` | 18 项用例逐条结果 + 5 处缺陷复盘 | — |
| `python/fastapi-demo/README.md` | 后端技术栈/结构/命令/限制 | 148 行 |
| `fullstack/product-admin/README.md` | 前端安装、脚本、目录 | — |

## 5. 技术栈与版本（实测）

| 层 | 组件 | 版本 | 证据 |
|---|---|---|---|
| 运行时 | Python | 3.15.0（CI 用 3.12） | `python3 -V` / `.github/workflows/ci.yml` |
| 后端 | FastAPI | 0.124.4 | `uv.lock（2026-11-07 起由 pyproject.toml 取代 requirements*.txt）` |
| | SQLAlchemy | 2.0.44（`Mapped`/`mapped_column`） | 同上 |
| | PyMySQL[rsa] | 1.1.2 | 同上 |
| | pydantic-settings | 2.12.0 | 同上 |
| 数据库 | MySQL | 8.4.13（本机 Homebrew） | `mysql --version` |
| 前端 | Node.js | v24.21.0 | `node -v` |
| | pnpm | 12.10.1（`pnpm-lock.yaml` 已提交） | `pnpm -v` |
| | Vue / Vue Router | ^3.5.13 / ^4.5.0 | `package.json` |
| | Vite / TypeScript | ^6.0.7 / ~5.7.3 | 同上 |
| | Element Plus | ^2.9.1 | 同上 |
| 工具链 | ruff 0.17.3 / pytest 9.2.0 / pre-commit 4.7.0 | 声明于 `pyproject.toml` 的 `[dependency-groups].dev`，锁定于 `uv.lock` | — |

## 6. 规模与质量基线

| 指标 | 数值 | 来源 |
|---|---|---|
| Git 跟踪文件 | 91 个 | `git ls-files \| wc -l` |
| 后端源码 | 1085 行（`app/`） | `wc -l` |
| 后端测试 | 237 行 / 23 用例 | 同上 |
| 前端源码 | 2674 行（`src/`） | 同上 |
| 文档 | 2812 行（40 个 Markdown） | 同上 |
| 静态检查 | `ruff check .` → All checks passed | 2026-11-06 复跑 |
| 测试 | `23 passed, 1 warning in 0.38s` | 2026-11-06 复跑 |
| CI | 2 次运行全部 success（2026-11-05） | `gh run list` |

## 7. 运行方式（现行）

```bash
# 后端（端口 8000）
cd python/fastapi-demo
cp .env.example .env          # 填 DATABASE_URL
.venv/bin/python -m app.init_db
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端（端口 5173）
cd fullstack/product-admin
pnpm install && pnpm dev

# 质量与验收
cd python/fastapi-demo && make check        # ruff + format + pytest
cd fullstack/product-admin && pnpm build && pnpm acceptance
```

## 8. 已具备的工程化能力

| 能力 | 状态 | 覆盖范围 |
|---|---|---|
| 格式化 / 静态检查 | ✅ ruff（format + lint） | 仅后端 |
| 单元/接口测试 | ✅ pytest 23 例 | 仅后端，且不连库 |
| 提交前检查 | ✅ pre-commit（ruff + 空白/大文件/私钥扫描） | 仅后端文件 |
| CI | ✅ GitHub Actions | 仅后端（无前端、无 MySQL 集成） |
| 一键命令 | ✅ Makefile（install/run/test/lint/fmt/check） | 仅后端 |
| 环境变量模板 | ✅ `.env.example` | 仅后端 |
| E2E 验收脚本 | ✅ 18 项 | 仅前端（依赖本地起的服务） |
| 容器化 / 部署 / 迁移 | ❌ 无 | — |

## 9. 与长期目标的差距（摘要）

1. **只有业务样板，没有 Agent 内核**：无 LLM 调用、无工具编排、无 MCP/RAG 代码。
2. **只有后端 CI**：前端无 lint、无单测、无 CI；后端无集成测试。
3. **零部署能力**：无 Dockerfile / compose / 反代 / 健康检查 / 发布脚本。
4. **零桌面打包能力**：未评估 Tauri / Electron 与 Python 后端的组合方式。
5. **数据库无迁移**：`create_all` 建表，无法演进 schema。
6. **AI 协作基建缺失**：角色定义、任务板、产出模板尚未固化为仓库资产（本阶段正在补）。

详见 `TECHNICAL_DEBT.md` 与 `REUSE_CANDIDATES.md`。
