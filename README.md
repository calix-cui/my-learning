# My Agent

一个用于学习 AI Agent 应用开发的全栈项目仓库。当前的可运行成果是 **My Agent 对话应用**：
Vue 3 聊天界面 + FastAPI 接口 + MySQL 落库，模型层可切换（默认假实现，配置后可接 DeepSeek 等 OpenAI 兼容服务）；
既能本地热更新开发，也能一条命令容器化部署。

> 商品管理后台（商品 / 分类 / 概览）已于 2026-11-08 整体归档到 [`archive/product-admin/`](archive/product-admin/README.md)，代码与文档都还在，只是不再随应用发布。

| 项 | 状态 |
|---|---|
| 功能 | 对话：多会话、消息落库、流式回复（SSE）、Markdown 渲染、自动命名、删除确认 |
| 模型 | 默认 `LLM_PROVIDER=fake`（不联网、可离线演示）；配 `openai` + Key 即接真实模型 |
| 验收 | 对话端到端 10/10；后端 75 个单测 + 覆盖率 91%；前端 32 个单测 |
| CI | GitHub Actions 双 job 全绿（ruff / pytest / ESLint / Vitest / build） |
| 部署 | Docker Compose 三容器 healthy，`/healthz` `/readyz` 探针可用 |

## 快速开始

### 方式一：本地开发（日常开发用这个）

前置：Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node 22+、[pnpm](https://pnpm.io/)、MySQL 8。

最简单的方式是一条命令起前后端（两边都带热更新）：

```bash
cp backend/.env.example backend/.env   # 填数据库密码（.env 不进版本库）
cd backend && uv sync && make migrate  # 装依赖 + 建表（首次）
cd .. && ./scripts/dev.sh              # 前端 :5173、后端 :8000，Ctrl-C 一起停
```

想分开起也可以：

```bash
# 终端 A：后端
cd backend && make run                 # uvicorn --reload，http://127.0.0.1:8000/docs

# 终端 B：前端
cd frontend && pnpm dev                # Vite HMR，http://127.0.0.1:5173（/api 代理到 8000）
```

接真实模型（可选）：在 `backend/.env` 里填 `LLM_PROVIDER=openai`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，
详见 [backend/README.md](backend/README.md) 的「接入真实模型」。不配就是假模型，照样能跑通全链路。

### 方式二：容器一键起（交付验证用，不是开发用）

前置：[Docker Desktop](https://www.docker.com/products/docker-desktop/)（或 colima + docker compose 插件）。

```bash
cp .env.example .env                # 改掉数据库密码
docker compose up -d --build
open http://localhost:8080
```

细节见 [部署文档](docs/deploy.md)。

> **什么时候用哪个**：改代码就用方式一——Vite HMR 与 `uvicorn --reload` 都是秒级生效，容器每改一次都要重打镜像、重装依赖（几分钟到十几分钟，还依赖网络）。
> 方式二只在**交付前验证**、给别人演示或验收「一键部署」时用；它跑的是镜像里的代码，改了源码不重建就不会生效。
> 两者都用同一个 Alembic 结构，但数据是分开的：本地库和容器卷里的数据互不影响。

## 目录结构

```text
my-learning/
├── backend/                 # 后端：FastAPI + SQLAlchemy + Alembic + LLM 抽象 + pytest
├── frontend/                # 前端：Vue 3 + TS + Vite + Element Plus + Vitest
├── docs/                    # 全部文档，入口见 docs/README.md
├── archive/product-admin/   # 已归档的商品管理模块（代码 + 文档，不参与构建）
├── deploy/Caddyfile         # 可选：Caddy 反向代理（HTTPS）
└── docker-compose.yml       # db / backend / frontend / 可选 caddy
```

`agent/`、`desktop/` 是后续阶段预留目录，当前不存在。

## 文档怎么读

**别从文件树开始翻。** 先读 [docs/README.md](docs/README.md)——它给出三条阅读路径（10 分钟 / 40 分钟 / 要动手改），以及每个文档「给谁看、什么时候看」。

最常用的三个：

- 想搞懂代码怎么跑 → [docs/how-it-works.md](docs/how-it-works.md)（含架构图、请求时序、数据模型）
- 想搞懂工具怎么用 → [docs/toolchain.md](docs/toolchain.md)（含工具链流程图）
- 想知道进度到哪了 → [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)

## 常用命令

| 我要 | 命令 | 目录 |
|---|---|---|
| 后端自检（lint + 测试 + 覆盖率） | `make check` | `backend` |
| 生成/应用数据库迁移 | `make revision m="说明"` / `make migrate` | `backend` |
| 前端自检（lint + 测试 + 构建） | `pnpm lint && pnpm test && pnpm build` | `frontend` |
| 对话端到端验收（需先起前后端） | `pnpm acceptance:chat` | `frontend` |
| 起整套容器 | `docker compose up -d --build` | 仓库根 |

## 通用约定

1. 一个目录对应一个边界清晰的项目，各自维护依赖与 README。
2. 依赖用 `uv.lock` / `pnpm-lock.yaml` 锁定并提交，不手写 `requirements.txt`，不混用包管理器。
3. 不提交密钥、虚拟环境、构建产物；真实配置放 `.env`，模板放 `.env.example`。
4. 改代码必须同一次提交里改对应文档（见 [docs/README.md](docs/README.md) §4「事实只有一个来源」）。
5. 重要技术选择写进 [docs/adr/](docs/adr/README.md)，不写在聊天记录里。

## 安全提醒

`.env.example` 只放变量名与示例值；`.env`、`*.pem`、私钥、令牌一律不进版本库。CI 里有 `detect-private-key` 钩子兜底。
