# Learning Lab · 商品管理后台

一个用于学习 AI Agent 应用开发的全栈项目仓库。当前的可运行成果是**简易商品管理网站**：
Vue 3 管理后台 + FastAPI 接口 + MySQL，既能本地开发，也能一条命令容器化部署。

| 项 | 状态 |
|---|---|
| 功能 | P0 十六条需求全部实现（商品增删改查、搜索筛选、分类管理、概览） |
| 验收 | 端到端 18/18 通过；后端 55 个单测 + 覆盖率 85.38%；前端 17 个单测 |
| CI | GitHub Actions 双 job 全绿（ruff / pytest / ESLint / Vitest / build） |
| 部署 | Docker Compose 三容器 healthy，`/healthz` `/readyz` 探针可用 |

## 快速开始

### 方式一：本地开发（推荐先跑这个）

前置：Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node 22+、[pnpm](https://pnpm.io/)、MySQL 8。

```bash
# 1) 后端
cd python/fastapi-demo
cp ../../.env.example .env          # 填数据库密码（.env 不进版本库）
uv sync                             # 按 uv.lock 装依赖
make migrate                        # 建表（Alembic）
uv run python -m app.seed           # 可选：写入演示数据
make run                            # http://127.0.0.1:8000/docs

# 2) 前端（另开一个终端）
cd fullstack/product-admin
pnpm install
pnpm dev                            # http://127.0.0.1:5173（/api 代理到 8000）
```

### 方式二：容器一键起

前置：[Docker Desktop](https://www.docker.com/products/docker-desktop/)（或 colima + docker compose 插件）。

```bash
cp .env.example .env                # 改掉数据库密码
docker compose up -d --build
open http://localhost:8080
```

细节见 [部署文档](docs/deploy.md)。

## 目录结构

```text
my-learning/
├── python/fastapi-demo/     # 后端：FastAPI + SQLAlchemy + Alembic + pytest
├── fullstack/product-admin/ # 前端：Vue 3 + TS + Vite + Element Plus + Vitest
├── docs/                    # 全部文档，入口见 docs/README.md
├── deploy/Caddyfile         # 可选：Caddy 反向代理（HTTPS）
└── docker-compose.yml       # db / backend / frontend / 可选 caddy
```

`frontend/`、`agent/` 是后续实验预留目录，当前不存在。

## 文档怎么读

**别从文件树开始翻。** 先读 [docs/README.md](docs/README.md)——它给出三条阅读路径（10 分钟 / 40 分钟 / 要动手改），以及每个文档「给谁看、什么时候看」。

最常用的三个：

- 想搞懂代码怎么跑 → [docs/how-it-works.md](docs/how-it-works.md)（含架构图、请求时序、数据模型）
- 想搞懂工具怎么用 → [docs/toolchain.md](docs/toolchain.md)（含工具链流程图）
- 想知道进度到哪了 → [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)

## 常用命令

| 我要 | 命令 | 目录 |
|---|---|---|
| 后端自检（lint + 测试 + 覆盖率） | `make check` | `python/fastapi-demo` |
| 生成/应用数据库迁移 | `make revision m="说明"` / `make migrate` | `python/fastapi-demo` |
| 前端自检（lint + 测试 + 构建） | `pnpm lint && pnpm test && pnpm build` | `fullstack/product-admin` |
| 端到端验收（需先起前后端） | `pnpm acceptance` | `fullstack/product-admin` |
| 起整套容器 | `docker compose up -d --build` | 仓库根 |

## 通用约定

1. 一个目录对应一个边界清晰的项目，各自维护依赖与 README。
2. 依赖用 `uv.lock` / `pnpm-lock.yaml` 锁定并提交，不手写 `requirements.txt`，不混用包管理器。
3. 不提交密钥、虚拟环境、构建产物；真实配置放 `.env`，模板放 `.env.example`。
4. 改代码必须同一次提交里改对应文档（见 [docs/README.md](docs/README.md) §4「事实只有一个来源」）。
5. 重要技术选择写进 [docs/adr/](docs/adr/README.md)，不写在聊天记录里。

## 安全提醒

`.env.example` 只放变量名与示例值；`.env`、`*.pem`、私钥、令牌一律不进版本库。CI 里有 `detect-private-key` 钩子兜底。
