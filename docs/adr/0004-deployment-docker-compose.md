# ADR-0004：用 Docker Compose 做单机一键部署

> **AI 向文档**：架构决策记录，人与 AI 共读；每条决策的「为什么」是重点。总入口见 [`../README.md`](../README.md)。

- 状态：已采纳（2026-11-07）
- 相关文档：[部署指南](../deploy.md)、[ADR-0001 桌面端 Electron](./0001-desktop-shell-electron.md)

## 背景

项目要能「本地开发 + 一键部署到云服务器」。当前本地跑法是「装 Python + 建 venv + 手起 uvicorn + 再起 Vite」，换台机器就要重来一遍，且 MySQL 版本、字符集、初始化顺序全靠口头约定。AGENTS.md 也要求从第一天就准备 Docker 化、环境变量管理、数据持久化与健康检查。

## 决策

用**一个 `docker-compose.yml` 编排四个服务**：

| 服务 | 形态 | 职责 |
| --- | --- | --- |
| `db` | 官方 `mysql:8.4` | 数据持久化在命名卷 `db-data` |
| `backend` | 多阶段构建（uv 建 venv → slim 运行层） | 启动先 `alembic upgrade head` 再起 uvicorn |
| `frontend` | 多阶段构建（node 构建 → nginx 托管） | 静态资源 + `/api` 反代到 backend |
| `caddy` | 官方 `caddy:2.9-alpine`，`profiles: ["https"]` | 可选的反向代理与 HTTPS 入口 |

配套：根目录 `.env.example` 存部署变量（复制成 `.env`）、`deploy/Caddyfile`、`docs/deploy.md`。

## 关键落地方式

1. **后端镜像用 uv 而不是 pip**：依赖层只 `COPY pyproject.toml uv.lock`，源码改动不会让依赖层缓存失效；`uv sync --frozen --no-dev` 保证镜像里的依赖与 `uv.lock` 一致。
2. **迁移放在容器启动时**：`CMD` 是 `alembic upgrade head && uvicorn ...`，首次创建容器自动建表，重复启动幂等。不把迁移塞进镜像构建期——构建期连不上数据库。
3. **只有入口层暴露端口**：`backend`、`db` 不映射宿主机端口，流量只能经 `frontend`（或 `caddy`）进入。
4. **两级健康检查**：`/healthz` 不碰数据库（容器存活），`/readyz` 真执行 `SELECT 1`（就绪，失败返回 503）。compose 的 `depends_on.condition: service_healthy` 用它排序启动。
5. **HTTPS 默认不开**：内网联调只要 `docker compose up -d` 就能用 `http://localhost:8080`；需要证书时加 `--profile https`，`SITE_ADDRESS` 填域名，Caddy 自动申请。
6. **前端与后端的耦合只有一处**：nginx 里 `proxy_pass http://backend:8000`，浏览器看到的是同源请求，因此容器部署下不需要 CORS 白名单。

## 代价

- 首次构建要拉 5 个基础镜像（约 1GB 量级），冷启动慢。
- 镜像体积、内存占用比裸机大；单机 Compose 没有滚动发布和多副本。
- 镜像构建目前不在 CI 里，构建失败只能在本地暴露。
- Docker daemon 是新的本机依赖：macOS 上需要 Docker Desktop/colima，本项目验证环境用的是 colima。

## 被否方案

| 方案 | 否决原因 |
| --- | --- |
| 一个容器同时装 Node 构建与 Python | 运行时不需要 Node，镜像白白大几百 MB，职责也混 |
| 用 Nginx 当唯一入口并自己管证书 | 证书申请/续期要额外脚本，Caddy 一行搞定 |
| 直接上 Kubernetes | 当前是单机、单副本场景，运维复杂度远大于收益；等真有多副本需求再迁移 |
| 只在 CI 里构建镜像、本地不提供 compose | 违背「本地开发与部署同构」，排障时无法在本机复现 |
| 后端用 Gunicorn + 多 worker | 现在没有压测数据；先保证单进程可观测，worker 数属于调优项 |

## 复评触发

- 需要多副本/滚动发布，或单机资源成为瓶颈 → 评估容器编排方案。
- 镜像构建进入 CI 后，把「构建失败」纳入合并门禁。
- 若桌面端（Electron）需要复用同一套后端，评估把 backend 镜像作为 sidecar 的基础镜像。
