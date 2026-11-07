# REUSE_CANDIDATES — 可复用工具与方案调研

> **归档文档**：阶段性产物，不再更新。结论已并入正式文档，见 [`README.md`](README.md)。

> 调研采样日：2026-11-06。版本号/日期来自当日实拉 PyPI、npm registry、GitHub shields（star 为四舍五入值，非精确计数）。
> 本文只回答「**要不要用**」，不写安装教程。结论三档：**建议引入** / **暂缓（触发条件）** / **不建议**。
> 与 `AGENTS.md` §2.1「优先复用现有能力」对应：每引入一个工具，都要能说出它替代了什么手工工作。

**已拍板的决策**（2026-11-06，项目 owner）：

- 桌面端外壳 → **Electron**（见 [ADR-0001](../adr/0001-desktop-shell-electron.md)），调研中更轻的 Tauri 存档为备选。
- 前端质量门禁 → **轻量档**（见 [ADR-0002](../adr/0002-frontend-quality-gate-lite.md)）：不做 type-aware lint、不设覆盖率门槛、Playwright 暂缓。
- 下文表格的「本项目结论」已按这两条决策更新；原始调研数据（版本/维护状态）保持不变。

## 0. 判断基准

本项目是**单人维护的学习型全栈项目**，长期目标包含 Web + 桌面 + Agent 能力。据此设五条硬约束，任何候选先过这五关：

1. **单机可跑**：不引入需要 K8s / 云服务托管的组件。
2. **可回退**：引入后能在半天内移除，不产生数据格式锁定。
3. **能搜到答案**：社区活跃、文档完整——出错时能自救（学习项目尤其重要）。
4. **与现有栈同构**：优先选已装工具（uv、pnpm、ruff）覆盖的能力，而不是再加一套。
5. **不提前抽象**：为「以后可能」付的成本，优先级低于当前阶段交付。

## 1. 结论速览

| 领域 | 建议引入 | 暂缓（触发条件） | 不建议 |
|---|---|---|---|
| Python 依赖 | **uv 统一依赖源**（pyproject + uv.lock） | — | pip-tools、Poetry、python-dotenv 直装 |
| 数据库迁移 | **Alembic** | — | — |
| 配置 | 保持 pydantic-settings | 多环境拆分（有 staging 时） | dynaconf 等叠加层 |
| 后端运行 | **uvicorn `--workers`** | gunicorn（已有 gunicorn 运维时） | — |
| 日志 | **structlog**（与容器化同批） | — | loguru |
| 测试 | **pytest-cov 覆盖率门槛**、polyfactory | httpx AsyncClient、factory_boy、testcontainers | — |
| 前端质量 | **ESLint 10 flat（轻量档）+ Prettier + Vitest（仅纯逻辑）** | oxlint（作 pre-commit 快跑补充） | Biome（Vue 支持仍实验性） |
| E2E | 暂用 `scripts/acceptance.mjs` | **Playwright**（用例 > 30 再换） | — |
| 部署 | **多阶段 Dockerfile + Compose + Caddy + 仓内 deploy.sh + /healthz** | appleboy/ssh-action | Nginx（当前场景过剩） |
| 桌面端 | **Electron + electron-builder + PyInstaller onedir**（ADR-0001） | Tauri v2（包体成为硬约束时再评估）、Nuitka（二期） | Wails |
| Agent 应用层 | **MCP Python SDK（先做 client）**、OpenAI Agents SDK（先 PoC） | LangGraph、LlamaIndex | CrewAI |
| Monorepo | 暂不动 | pnpm workspace（出现 desktop/ 或共享包时） | Turborepo、Nx |

## 2. Python 依赖与迁移

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| [uv](https://github.com/astral-sh/uv) | 装包/锁/venv/工具一体 | 0.13.7 / 2026-11-03 / 92k★ | **建议引入（深化）**：本机已装（0.13.4），但依赖仍写在 `requirements*.txt`，`pyproject.toml` 只放工具配置。把 `[project.dependencies]` 定为唯一来源 + `uv.lock` 提交，CI 用 `uv sync --frozen`。 |
| [pip-tools](https://github.com/jazzband/pip-tools) | requirements.in → 锁 txt | 7.6.2 / 2026-10-07 / 8k★ | **不建议**：能力被 uv 全覆盖，引入即多一套锁格式。 |
| [Poetry](https://github.com/python-poetry/poetry) | 打包+依赖+发布 | 2.5.1 / 2026-09-20 / 34k★ | **不建议**：已有 uv，迁移只增心智负担。 |
| **Alembic** [repo](https://github.com/sqlalchemy/alembic) · [autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) | SQLAlchemy 官方迁移 | 1.20.1 / 2026-10-22 / 4.5k★ | **建议引入**：解决 T-05。`create_all` 只建不改；autogenerate 对改名/约束/类型变更**有盲区，必须人工 review**；先用 `alembic stamp` 接管现有库再生成首个 revision。 |
| [pydantic](https://github.com/pydantic/pydantic) / [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 模型校验 / 分层配置 | 2.14.3 / 2026-11-05；2.16.2 / 2026-10-28 | **保持现状**：`SecretStr`、`env_nested_delimiter` 已够用，别叠 dynaconf。 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 手动加载 .env | 1.2.4 / 2026-10-01 | **不建议直装**：pydantic-settings 的依赖里已含（实拉元数据确认），显式声明只增冲突面。 |

## 3. 后端生产化

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| uvicorn `--workers N` | 多进程 | 0.54.0 / 2026-09-25 / 11k★ | **建议**：官方文档明确 spawn 模型在 Windows 也可用；`--reload` 与 `--workers` 互斥（调试配置里已因 reload 踩过坑）。 |
| [gunicorn](https://gunicorn.org/install/) + uvicorn worker | 预 fork 进程管理 | 26.2.0 / 2026-08-24，需 Python ≥ 3.12 | **不建议**：uvicorn 文档已把 `uvicorn.workers` 标为 **deprecated**；纯 uvicorn 少一层依赖。 |
| [structlog](https://github.com/hynek/structlog) | 结构化 JSON 日志 | 26.1.0 / 2026-06-06 / 5k★ | **建议（与容器化同批）**：解决 T-23；与标准 logging 互通，可统一 uvicorn/httpx 的日志。 |
| [loguru](https://github.com/Delgan/loguru) | 开箱日志 | 0.7.3 / 2024-12-06（近两年无发布） | **不建议**：替换 logging 后三方库日志难汇流，发布节奏脱节。 |

## 4. 测试

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| pytest + TestClient（现状） | 同步调 ASGI | pytest 9.2.0 / 2026-10-27 / 15k★ | **保持**：TestClient 本身就是 httpx 封装，换 httpx 零收益。 |
| [httpx](https://github.com/encode/httpx) AsyncClient + ASGITransport | 真异步测试 | 0.28.1 / 2024-12-06 / 16k★ | **暂缓**：当前无 async-only 路径（流式/lifespan 细节）才需要。 |
| [polyfactory](https://github.com/litestar-org/polyfactory) | 由 pydantic 模型生成假数据 | 3.5.0 / 2026-10-21 / 1.5k★ | **建议（低成本）**：与 pydantic v2 同源，替手写 fixture；正好补 T-04 的集成测试数据。 |
| [factory_boy](https://github.com/factoryboy/factory_boy) | ORM 模型工厂 | 3.3.3 / 2025-02-03 / 3.8k★ | **暂缓**：目前没有复杂对象图。 |
| [testcontainers-python](https://github.com/testcontainers/testcontainers-python) | 测试期拉真 MySQL | 4.15.0 / 2026-07-24 / 2.3k★ | **暂缓**：CI 需 DinD、拉镜像慢；等 Alembic 落地后只给 1 个 `@pytest.mark.integration` 用例启用。**注意：本机 Docker daemon 当前不可用（T-24）**。 |
| pytest-cov + [coverage](https://github.com/nedbat/coveragepy) | 覆盖率闸门 | 7.1.0 / 2026-03-21；7.17.2 / 2026-11-04 | **建议**：`--cov=app --cov-fail-under=70` 一行，把「新增代码带测试」变成 CI 可执行约束。 |

## 5. 前端质量

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| **ESLint 10 flat** + [typescript-eslint](https://github.com/typescript-eslint/typescript-eslint) + [eslint-plugin-vue](https://github.com/vuejs/eslint-plugin-vue) | 语义 lint（含 SFC/TS） | eslint 10.14.0 / 2026-10-30 / 28k★；ts-eslint peer 支持 `^8.57 \|\| ^9 \|\| ^10`；vue 插件 peer 同支持 10 | **建议引入（轻量档，ADR-0002）**：只开 `eslint:recommended` + `plugin:vue/vue3-essential` + ts-eslint `recommended`，**不开 type-aware**（类型正确性由 `vue-tsc --noEmit` 兜底）。flat config 单文件即可，别装 @vue/cli 系列；eslint 10 要求 node `^20.19 \|\| ^22.13 \|\| >=24`（本机 24.21 满足）。 |
| [oxlint](https://oxc.rs/docs/guide/usage/linter/type-aware.html) | Rust 极速 lint | 1.91.0 / 2026-11-03 / 23k★ | **暂缓（补充层）**：type-aware 需 oxlint-tsgolint；`.vue` 靠第三方 `oxlint-vue`，不宜作唯一 lint。可做 pre-commit 的 200ms 快跑。 |
| [Prettier](https://github.com/prettier/prettier) | 纯格式化 | 3.9.10 / 2026-10-10 / 52k★ | **建议引入（轻量档）**：与 ESLint 职责分离（`eslint-config-prettier` 关冲突），**只在保存时/需要时执行，不进 CI 阻断**。 |
| [Biome](https://biomejs.dev/internals/language-support/) | lint+format 二合一 | 2.6.5 / 2026-11-04 / 26k★ | **不建议（现在）**：[语言支持表](https://biomejs.dev/internals/language-support/) 里 Vue 标 🟡（v2.3.0 起实验性），替换双工具的收益小于生态风险。 |
| **Vitest** + [@vue/test-utils](https://github.com/vuejs/test-utils) | 单元/组件测试 | 5.1.0 / 2026-11-02 / 17k★（Node ≥ 22.12）；2.5.1 / 2026-09-16 | **建议引入（轻量档）**：只覆盖 `src/api`、`src/utils` 这类纯逻辑，**不写组件快照、不设覆盖率门槛**；复用 Vite 配置零额外构建。 |
| [Playwright](https://github.com/microsoft/playwright) | E2E + runner + trace | 1.65.0 / 2026-11-05 / 99k★ | **暂缓**：`scripts/acceptance.mjs`（18 项）目前够用；**触发条件**：E2E 用例 > 30 条，或出现「改一处坏一片」且现有脚本没拦住的事故 ≥ 2 次。那时再迁移，收益才大于胶水成本。 |
| puppeteer-core（现状） | 驱动本地 Chrome | 25.16.0 / 2026-10-22 / 96k★ | **暂用**：无 runner/断言体系，手工管 Chrome 路径、跨平台易碎（本次已验证要 `--no-sandbox --user-data-dir`）。作为 Playwright 迁移前的过渡方案保留。 |

## 6. 部署

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| 多阶段 Dockerfile（uv 官方镜像 copy 模式） | 构建/运行分离 | Docker 29.x CLI 可用；uv 提供 `ghcr.io/astral-sh/uv` | **建议**：builder 装依赖 → runtime 只带 venv + 源码，`uv sync --frozen` 保证与 lock 一致。 |
| [Docker Compose](https://github.com/docker/compose) | 单机多服务编排 | v5.7.0 / 39k★ | **建议**：app + mysql + caddy 一键起，与生产同构。**本机当前无 compose 子命令（T-24），需先装**。 |
| [Caddy](https://caddyserver.com/docs/automatic-https) | 反代 + 自动 HTTPS | v2.11.9 / 79k★ | **建议**：3 行 Caddyfile 拿到证书，比 Nginx + certbot 少一个定时任务。 |
| [Nginx](https://github.com/nginx/nginx) | 通用反代 | 32k★ | **不建议（当前）**：证书自动化要额外组件，功能过剩。 |
| [appleboy/ssh-action](https://github.com/appleboy/ssh-action) | Actions 内 SSH | v1.2.5 / 6.2k★ | **暂缓**：部署逻辑埋进 action 输入，版本漂移不可审计。 |
| 仓内 `scripts/deploy.sh`（ssh + compose pull/up） | 部署逻辑入库 | — | **建议**：Actions 只调用脚本，本地可复现；密钥走 Secrets。 |

## 7. 桌面端（Vue + Python FastAPI）

> **已决策：Electron**（[ADR-0001](../adr/0001-desktop-shell-electron.md)，2026-11-06）。下表结论按此更新，Tauri 保留为备选记录。

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| [Electron](https://github.com/electron/electron) | Chromium + Node 壳 | 45.2.3 / 2026-11-04 / 124k★ | **采用（ADR-0001）**：主进程 `child_process.spawn` 直接拉起打包后的 Python 后端，管理端口与生命周期；`electron-builder` 覆盖三平台安装包与自动更新。代价是包体（量级 100MB+，**未实测**）与内存占用。 |
| **Tauri v2** [repo](https://github.com/tauri-apps/tauri) · [sidecar](https://v2.tauri.app/develop/sidecar/) | Rust 壳 + 系统 WebView，外部二进制作 sidecar | 2.12.4（CLI）/ 2026-10-21 / 113k★ | **未采用（备选存档）**：包体更小，但需 Rust 工具链 + `externalBin` 按 `<name>-<target-triple>` 命名、每平台单独构建。**触发重评**：包体或冷启动成为硬指标时（首次对外分发前）。 |
| [Wails](https://github.com/wailsapp/wails) | Go 壳 + 系统 WebView | v3.1.0 / 37k★ | **不建议**：需 Go 工具链，且没有一等 Python sidecar 机制。 |
| [electron-builder](https://github.com/electron-userland/electron-builder) | 打包/签名/自动更新 | 跟随 Electron 生态 | **建议**：与 Electron 配套，`dmg`/`nsis`/`AppImage` 一次配置三平台产出。 |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) / [Nuitka](https://github.com/Nuitka/Nuitka) | 把 FastAPI 打成可执行载荷 | 6.22.3 / 2026-09-12；4.3.4 / 2026-11-01 | **建议 PyInstaller 先上**：桌面用 `--onedir`（`--onefile` 冷启动慢）；Nuitka 二期再评估。 |

**组合建议**：Electron（主进程 spawn 子进程）+ PyInstaller `--onedir` 打包后端 + 复用现有 `vite build` 产物。桌面端后端**固定单 worker、随机本地端口**，启动时下发一次性 token 做本地鉴权——否则无鉴权的 API 会暴露在 localhost。

## 8. AI Agent 应用层（方向性）

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | agent/tool/handoff/guardrail 原语 | 0.24.0 / 2026-10-15 / 31k★ | **建议（先 PoC）**：抽象薄、与 FastAPI 同构，可指向兼容 `base_url`；但仍是 0.x，API 会动。 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 图状态机 + checkpoint | 1.2.20 / 2026-11-05 / 45k★ | **暂缓**：多步可恢复/HITL 才需要；checkpoint 抽象会绑数据模型。 |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MCP client/server | 2.3.0 / 2026-10-02 / 25k★ | **建议（尽早）**：工具接入的事实标准；先写 client 接现成 MCP server，别自造协议。 |
| [LlamaIndex](https://github.com/run-llama/llama_index) | 检索/索引/RAG | 0.14.25 / 2026-09-21 / 53k★ | **暂缓**：没有 RAG 需求，提前引入会锁死向量库选型。 |
| [CrewAI](https://github.com/crewAIInc/crewAI) | 角色化多 agent | 1.15.36 / 2026-11-06 / 61k★ | **不建议**：角色扮演叙事与本项目「可调试的应用级 Agent」目标错位。 |

## 9. Monorepo

| 候选 | 用途 | 维护状态 | 本项目结论 |
|---|---|---|---|
| [pnpm workspace](https://pnpm.io/workspaces) | 共享 lock/依赖 | pnpm 37k★ | **暂缓（条件触发）**：出现 `desktop/` 或 `packages/shared` 时再做，根提升约 10 分钟。 |
| [Turborepo](https://github.com/vercel/turborepo) | 任务图 + 缓存 | 2.11.10 / 2026-10-20 / 31k★ | **暂缓（倾向不做）**：2 个包、无共享构建产物时缓存收益 ≈ 0。 |
| [Nx](https://github.com/nrwl/nx) | 生成器 + 项目图 | 24.0.4 / 2026-11-03 / 29k★ | **不建议**：生成器的强约束与小步手写冲突。 |

## 10. 两个项目特定事实（影响上面的结论）

1. ~~**uv 已装但未承担依赖声明**~~ ✅ 2026-11-07 已改造：`pyproject.toml` 的 `[project.dependencies]` 是唯一来源，`uv.lock` 锁定，`requirements*.txt` 已删除，CI 用 `uv sync --frozen`。
2. **`pnpm-workspace.yaml` 在子目录**：`fullstack/product-admin/pnpm-workspace.yaml` 只放了 `allowBuilds`，仓库根没有 workspace。任何 monorepo 工具在提升到根之前都不成立。

## 11. Top 5（按收益/成本比，已按 2026-11-06 决策调整）

1. **Alembic** — 数据演进是上线硬门槛，成本约半天（`stamp` 现有库 + 首个 revision）。**[P0]**
2. **ESLint 10 flat（轻量档）+ Prettier + 前端 CI job（`pnpm build` + `pnpm lint`）** — 只拦明显错误，不做 type-aware、不设覆盖率门槛；配置约 40 行，新增摩擦≈0。**[P0]**
3. **uv 统一依赖源（pyproject + uv.lock + `uv sync --frozen`）** — 消除手工锁版本漂移，CI 与 Docker 可复现，成本半天。**[P0]**
4. **Docker 多阶段 + Compose + Caddy + `/healthz`** — 打通「一键部署」首个可交付里程碑；桌面端（Electron + PyInstaller）后续复用同一份后端产物。**[P1，依赖 T-24 先装 Docker]**
5. **Vitest（仅纯逻辑）+ pytest-cov 门槛（仅后端）** — 后端设覆盖率门槛、前端只测 `src/api`/`src/utils`，两端成本都在半天内。**[P1]**

> 排序理由：前三条是「阻止继续产生新债」，后两条是「补齐交付能力」。前端门禁刻意做轻（ADR-0002）——门禁的价值是「拦住的 bug ÷ 增加的摩擦」，单人项目里 type-aware lint 与覆盖率门槛的摩擦大于收益。

## 12. 未核实项（不要当成结论）

- 桌面框架的实际安装包体积/内存：**未实测**；Tauri 官方称「系统 WebView 包更小」，Electron 的 100MB+ 量级来自社区普遍观察，本项目未秤过。
- PyInstaller `--onedir` 与 Nuitka 的启动耗时对比：未实测。
- star 数为 shields 四舍五入值（如 92k），非精确计数；API 当日限流。
- testcontainers 在本机/CI 的可行性：**未验证**，且当前 Docker daemon 不可用。
