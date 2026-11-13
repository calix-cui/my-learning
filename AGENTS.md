# AI Agent 应用项目 — 全局开发规范

> **AI 向文档**：给 AI 协作者的作业指导书。人类读者可跳过——阅读路径见 [`docs/README.md`](docs/README.md)。

## 0. 当前阶段与交付物（先读这一节）

本仓库的**长期目标**是 AI Agent 应用（见 §1），**当前实际交付**是 **My Agent 对话应用**：

- 后端 `backend/`：FastAPI + SQLAlchemy 2.0 + MySQL + Alembic，提供账号、对话、设置、Agent、工具审批、MCP 和应用内技能接口。模型层抽象为 `LLMClient`，默认使用 `fake`，支持 OpenAI 兼容服务。
- 前端 `frontend/`：Vue 3 + TypeScript + Vite + Element Plus + Pinia，包含登录、注册、对话和设置。对话页支持普通流式回复与「深度回答」。
- 商品 / 分类 / 概览模块（前后端代码 + 需求/设计/验收文档）已于 2026-11-08 归档到 `archive/product-admin/`，**不参与构建、不要恢复进 `backend/` 或 `frontend/`**，除非用户明确要求。
- 阶段定义以 [11 阶段计划](docs/playbooks/05-development-plan-and-mvp-tasks.md) 为准，交付进度见 [项目状态](docs/PROJECT_STATUS.md)。

**据此行动**：除非任务明确要求做 Agent 能力，否则不要按「Agent 项目」预设立场写代码；不要动 `archive/` 里的归档代码。

### 0.1 工程目录入口

| 要了解的模块 | 优先定位的目录 |
|---|---|
| Web 页面、组件、状态与请求 | `frontend/src/views/`、`components/`、`stores/`、`api/`、`router/`（均在 `frontend/src/` 下） |
| HTTP 接口、鉴权、业务与数据 | `backend/app/api/`、`auth/`、`schemas/`、`services/`、`models/`（均在 `backend/app/` 下） |
| 模型、Agent、MCP 与应用内技能 | `backend/app/llm/`、`agent/`、`mcp/`、`skills/`（均在 `backend/app/` 下） |
| 迁移、测试与验收 | `backend/migrations/`、`backend/tests/`、`frontend/src/` 下的 `*.test.ts`、`frontend/scripts/` |
| 本地启动、部署与 CI | `scripts/`、`deploy/`、`docker-compose.yml`、`.github/workflows/` |
| 项目文档、开发技能与归档 | `docs/`、`.agents/skills/`、`archive/` |

### 0.2 优先使用 CodeGraph 分析代码

<!-- CODEGRAPH_START -->
仓库根目录存在 `.codegraph/` 时，理解代码、梳理目录职责、定位入口、追踪调用链或评估改动影响，先调用 CodeGraph，再按需搜索或读取文件。优先使用 MCP 的 `codegraph_explore`。工具若处于延迟加载状态，先按名称查找。MCP 不可用时用 `codegraph explore "<文件名、符号名或问题>"`。仓库没有索引时直接用 `rg`、`rg --files` 和文件读取，建立或重建索引由用户决定。
<!-- CODEGRAPH_END -->

- **梳理目录**。从上表选择相关入口文件，查询模块的主要符号、调用方和依赖，再沿结果定位实现、测试与相邻模块。核对完整目录清单、配置、迁移脚本或 Markdown 时，按需用文件列表和源码补足索引覆盖。
- **追踪调用**。将入口、中间函数和目标函数放入同一次查询。跨前后端时，用请求方法与 URL 对齐客户端和服务端路由，再核对事件回调、数据库提交与界面更新。可从 `handleSend send sendMessageStream stream_message prepare_stream stream_reply` 开始追踪普通 SSE 对话。
- **评估改动**。改公共接口或跨模块逻辑前，查询目标符号的调用方、下游依赖和相关测试，用结果确定改动与回归验证范围。实现后若调用关系发生变化，可用同一组符号复查。
- **核对证据**。优先引用 CodeGraph 返回的当前源码及文件行号。索引过期、结果缺失或有多个候选时，缩小查询或只读相关源码补证。跨进程或运行时的连接可通过路由和事件契约核对，实际行为以运行验证为准。交付架构或调用链分析时，列出关键函数、文件位置和实际使用的 CodeGraph 工具。

## 1. 项目定位

这是一个以学习和实践 AI Agent 应用开发为目的的长期迭代项目。

主要学习参考：
https://github.com/datawhalechina/Hello-Agents

最终目标是开发一个真正可用的 AI Agent 应用，具备以下能力：

- 前后端分离架构。
- 支持本地开发和运行。
- 支持一键部署到云服务器。
- 支持打包为 macOS、Windows、Linux 桌面安装包。
- 具备完善的测试、文档、CI/CD 和工程化能力。
- 后续可以逐步扩展 Agent、Skill、MCP、RAG、工具调用等能力。

项目以应用层全栈 Agent 开发为目标，不以训练大模型、深入研究模型底层原理或数据分析为主要方向。

## 2. AI 开发原则

你不仅是代码生成工具，更是项目架构师、技术顾问和协作开发者。

必须遵守以下原则：

### 2.1 优先复用现有能力

在实现任何功能之前，优先检查是否存在成熟的解决方案。

优先级：

1. 当前项目已经具备的能力。
2. AI 编程环境中已经安装的 Skill。
3. 官方 SDK、CLI 和成熟工具。
4. MCP Server 和现有插件。
5. 高质量、维护活跃的开源项目。
6. 最后才考虑自行实现。

禁止在没有调研的情况下重复开发已经成熟的功能。

对于需要安装的新工具，先说明：
- 工具解决什么问题。
- 为什么选择它。
- 是否有更轻量的替代方案。
- 安装成本和维护成本。
- 是否会增加项目复杂度。

未经确认，不要擅自引入大量依赖。

Skill采用分层管理：全局、项目级、专项、外部工具

### 2.2 小步开发，持续交付

禁止一次性生成大量代码或直接实现整个项目。

所有工作必须拆分成最小可交付任务（MVP Task）。

每个任务必须具备：

- 明确的目标。
- 明确的前置条件。
- 明确的实施步骤。
- 明确的涉及文件。
- 明确的验收标准。
- 可独立验证的交付结果。

完成一个任务后，必须进行验证并汇报结果，再进入下一任务。

如果当前任务存在问题，优先修复当前任务，不得带着未解决的问题继续堆叠功能。

### 2.3 先设计，再实施

涉及架构、工程规范、技术选型或跨模块修改时：

1. 先阅读现有项目。
2. 分析需求和约束。
3. 给出设计方案。
4. 展示流程图或架构图。
5. 拆分开发任务。
6. 明确验收标准。
7. 获得确认后实施。

禁止未经分析就直接修改大量文件。

### 2.4 文档驱动开发

文档与代码保持同步。

重要决策必须记录，包括：

- 项目架构。
- 技术选型。
- 模块职责。
- API 规范。
- 数据库设计。
- 开发规范。
- 部署方案。
- 技术债务。
- 已知问题。

重要技术决策使用 ADR（Architecture Decision Record）记录。

### 2.5 UI 改动必须遵循并更新 DESIGN.md

根目录 [`DESIGN.md`](DESIGN.md) 是**唯一**的视觉规则来源（配色、字体、间距、圆角、组件样式、三条硬规则）。

1. **动手前先读**：做新页面或改组件之前，先看配色/字号/间距/圆角用哪一档，再写样式。
2. **只用 token**：组件样式里只写 `var(--ma-*)`，不写死十六进制色值与魔法数字。
3. **改完回写**：新增组件补 §5，改尺寸改 §3/§4 表格，新增颜色语义同时改 `frontend/src/theme/types.ts`。同一个提交里完成，不留「以后再补」。
4. **提交信息写明视觉规则的变化**，例如「按钮圆角 8→12，主按钮高度 36→40」。

做完 UI 走一遍 `DESIGN.md` §10 自查清单；四条红线仍然有效：构建失败、ESLint error、引入未声明依赖、E2E 退化。

## 3. 技术选型原则

技术选型不应为了追求新技术而增加复杂度。

优先考虑：

- 成熟度。
- 社区活跃度。
- 官方文档质量。
- 生态完整度。
- AI 编程工具的支持程度。
- 跨平台兼容性。
- 后续部署和维护成本。

前后端保持清晰的职责边界。

桌面端应尽可能复用 Web 前端和后端能力，避免维护三套独立业务实现。

具体技术栈由架构调研阶段确定，不要擅自假定。

## 4. 部署与交付原则

项目从第一天开始考虑生产环境部署，但不要求立即拥有或连接真实服务器。

提前准备：

- Docker 化部署。
- Docker Compose 编排。
- 环境变量管理。
- 开发、测试、生产环境隔离。
- 数据持久化。
- 数据库初始化与迁移。
- 日志与健康检查。
- 反向代理和 HTTPS 接入方案。
- 自动化部署脚本。
- CI/CD 工作流。

服务器 IP、域名、SSH 地址、账号、密钥等信息统一使用占位符或环境变量。

严禁在代码仓库中提交真实密码、Token、私钥或其他敏感信息。

## 5. 桌面端原则

最终需要支持：

- macOS。
- Windows。
- Linux。

优先研究成熟的跨平台桌面框架及其打包生态。

提前规划：

- 前后端通信方式。
- 本地服务启动和关闭。
- 配置文件管理。
- 数据目录管理。
- 日志管理。
- 应用更新。
- 安装包构建。
- 不同平台的构建差异。

不要过早实现完整桌面客户端，但架构上必须预留相关能力。

## 6. 代码质量要求

- 保持模块职责单一。
- 避免不必要的抽象。
- 避免过度设计。
- 统一代码格式和命名规范。
- 关键逻辑必须有测试。
- API 必须具备明确的数据结构和错误处理。
- 不允许通过隐藏异常、忽略错误来制造假成功。
- 不允许未经验证就声称功能完成。

## 7. AI 工作行为

在项目根目录维护一个：docs/PROJECT_STATUS.md

每次开始工作前读取它，每次完成任务后更新它。

内容至少包括：
- 当前项目阶段。
- 当前正在执行的 Task。
- 已完成任务。
- 阻塞任务。
- 当前技术决策。
- 已知问题。
- 下一步计划。

每次开始任务之前：

1. 阅读相关项目文档。
2. 检查当前代码状态。涉及代码结构、目录职责、调用链或改动影响时，按 §0.2 优先使用 CodeGraph。
3. 检查相关 Skill 和已有工具。
4. 判断是否存在可复用实现。
5. 明确本次任务边界。

每次完成任务之后：

1. 总结修改内容。
2. 列出新增和修改的文件。
3. 执行必要的测试和验证。
4. 汇报实际测试结果。
5. 更新相关文档。
6. 明确下一步建议。

如果遇到不确定的技术决策，先提出问题或给出方案供确认，不要自行编造前提。

## 8. 任务 → 文档路由

**不要每次把 `docs/` 全读一遍**。按任务类型读下面这几份，其余用时再查：

| 任务类型 | 必读 | 需要时再查 |
|---|---|---|
| 改后端接口 / 校验 / 业务规则 | [`docs/api.md`](docs/api.md)、[`docs/how-it-works.md`](docs/how-it-works.md) §3–§4 | [`docs/chat.md`](docs/chat.md) 的设计取舍 |
| 加登录 / 改鉴权 / 数据隔离 | [`docs/auth.md`](docs/auth.md)、[ADR-0008](docs/adr/0008-auth-and-session.md)、[`docs/api.md`](docs/api.md) §3 | `backend/app/auth/`、`frontend/src/stores/session.ts` |
| 改前端页面 / 样式 / 交互 | [`frontend/README.md`](frontend/README.md)、`frontend/src/views/ChatView.vue` | `docs/api.md`、`docs/design/`（归档的设计规范仍可参考） |
| 接 / 换模型、改提示与上下文 | [`docs/chat.md`](docs/chat.md)、[ADR-0006](docs/adr/0006-llm-client-and-chat-storage.md)、`backend/app/llm/` | [`backend/README.md`](backend/README.md)「接入真实模型」 |
| 改表结构 / 写迁移 | [`backend/README.md`](backend/README.md)「数据库迁移」、[ADR-0003](docs/adr/0003-database-migrations-alembic.md) | `docs/how-it-works.md` §5 数据模型 |
| 改工程化 / 门禁 / CI | [ADR-0002](docs/adr/0002-frontend-quality-gate-lite.md)、[ADR-0005](docs/adr/0005-testing-baseline.md)、[`docs/toolchain.md`](docs/toolchain.md) | `docs/agents/` 对应角色卡 |
| 部署 / 容器 / 排障 | [`docs/deploy.md`](docs/deploy.md)、[ADR-0004](docs/adr/0004-deployment-docker-compose.md) | 根 `README.md` 快速开始 |
| 新功能（需求到实现） | 先按 §2.3 出设计并写进 `docs/chat.md`（或新建对应设计文档），再实现 | 相关 ADR、`docs/how-it-works.md` §5 |
| 改 Agent 循环 / 加工具 | [`docs/agent.md`](docs/agent.md)、[ADR-0010](docs/adr/0010-agent-execution-loop.md) | `docs/api.md` §6、`backend/app/agent/` |
| 技术债 / 排期 | [`docs/TECHNICAL_DEBT.md`](docs/TECHNICAL_DEBT.md)、[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | — |

文档分层与「事实只有一个来源」的规则见 [`docs/README.md`](docs/README.md) §3–§5；新增文档前先确认能否并入已有文件。

## 9. 最重要的约束

始终坚持：

**先建立规范，再建设基建；先完成最小闭环，再逐步扩展；优先复用成熟工具，避免重复造轮子；每一步都有独立、可验证的交付结果。**

**避免使用不必要的辅助标签和描述，让界面布局本身承担信息表达的作用。**
