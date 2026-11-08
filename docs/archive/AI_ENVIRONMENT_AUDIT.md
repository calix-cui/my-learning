# AI_ENVIRONMENT_AUDIT — AI 开发环境审计

> **归档文档**：阶段性产物，不再更新。结论已并入正式文档，见 [`README.md`](README.md)。

> 调研时间：2026-11-06 · 环境：DSH Web（本会话）+ 本机 macOS (arm64)
> 原则：**只记录可验证的事实**。凡是"没看到 / 没验证"的，明确写「未确认」，不猜测。

## 0. 结论摘要

| 层 | 现状 | 缺口 |
|---|---|---|
| 规则文件 | 已有仓库级 `AGENTS.md`（规范）+ `docs/playbooks/1..7`（分阶段提示词），但**都未提交** | 缺项目级细则、缺 ADR 机制 |
| Skills | 会话内可用 8 个（Office 7 个 + 插件商店 1 个），全部是**通用办公/商店**类 | 与「AI Agent 开发」直接相关的 Skill 为 0；无项目级 Skill |
| MCP | DSH profile 配了 3 个（QQ 桥接 + 联网搜索），Codex 另配 2 个 | 本会话工具面**看不到** `mcp__*` 工具；无数据库/浏览器/文件系统类 MCP |
| CLI | git / gh / node / pnpm / uv / jq / make / mysql 齐全 | Docker 守护进程未运行且无 compose；ruff / pytest / pre-commit 只在项目 venv 内 |
| Agent/Prompt/Workflow | 有 7 阶段提示词流水线、CI workflow、Makefile、18 项验收脚本 | 无 subagent 角色定义、无任务板/产出模板、无「提示词 → 产出物」的落盘约定 |

一句话：**AI 协作的"输入侧"（规范与提示词）刚建立，"执行侧"（Skill / MCP / Agent / 自动化编排）基本空白。**

## 1. 规则文件层

| 文件 | 位置 | 谁在读 | 内容 | 状态 |
|---|---|---|---|---|
| `AGENTS.md` | 仓库根 | DSH（本次会话已注入为 workspace instructions） | 8 节：项目定位、AI 开发原则（复用优先/小步交付/先设计）、技术选型、部署、桌面端、代码质量、AI 工作行为、最重要的约束 | **未提交**（`git status`: `?? AGENTS.md`） |
| `docs/playbooks/1..7` | 仓库 docs | 人工按阶段喂给 AI | 1 认识项目 → 2 AI 基建 → 3 工程架构 → 4 部署与跨端 → 5 开发计划与 MVP 任务 → 6 单任务 → 7 code review | **未提交**（`?? docs/playbooks/`） |
| `CONTRIBUTING.md` | 仓库根 | 人（也是 AI 的隐含约束） | 新建项目流程、README 最低要求、依赖管理、提交规范 | 已提交 |
| `.vscode/settings.example.json` | 仓库 `.vscode` | VS Code | 解释器路径、pytest 配置、ruff 保存即格式化 | 已提交（示例） |
| `~/.codex/AGENTS.md` | 用户主目录 | Codex CLI | **空文件（0 行）** | 存在但无内容 |
| `~/.cursor/skills-cursor/` | 用户主目录 | Cursor IDE | 26 个 Cursor 内置 Skill | 与 DSH 会话无关 |

**结论**：DSH 已正确识别并注入仓库根 `AGENTS.md`（本会话 system-reminder 中可见全文），说明"仓库级规则"这条路是通的；但 `AGENTS.md` 还在工作区未提交，换机器/换会话会丢。

## 2. 已安装的 Skills（本会话可见）

DSH 会话目录共 8 个，来源是 profile bundles（`@deepseek-ai/dsh-base` 等）自带的资源包，不是项目自建：

| Skill | 一句话能力 | 与本项目相关性 |
|---|---|---|
| `office` | Office 文档总入口，选择合适工作流 | 低（写 PRD/报告时可能用到） |
| `office-docx` | 创建/读取/编辑/校验 Word | 低 |
| `office-pptx` | 创建/读取/编辑/校验 PPT | 低 |
| `office-xlsx` | 读写 Excel、公式与数据 | 低 |
| `office-recalculate` | 用 LibreOffice 重算表格公式缓存 | 极低 |
| `office-render` | 把文档渲染成图片/检查版式 | 低（可用于验收截图排版） |
| `office-export-pdf` | Office → PDF | 低 |
| `search-dsh-store` | 查询 DSH 插件商店、安装/更新 Web 插件 | 中（未来装插件时用） |

**未发现项目级 Skill 目录**（未在仓库内发现 `skills/`、`.dsh/skills/` 等被启用的约定）。

> 说明：上表依据**会话内 Skill 目录中的能力描述**判断，未逐一展开每个 `SKILL.md` 正文——这些定义打包在 DSH 应用 bundle 内（`app.asar`），不是仓库或主目录下的松散文件。8 个 Skill 均为 Office/商店类，与本项目（Web 全栈 + Agent）无直接耦合，因此逐一精读的收益很低；若后续要基于某个 Skill 扩展，再用 `skill` 工具加载全文核对。

**主目录另有 Cursor 的 26 个 Skill**（`~/.cursor/skills-cursor/*/SKILL.md`），含 `create-subagent`、`create-skill`、`review`、`split-to-prs`、`visualize` 等。这些属于 Cursor IDE，**DSH 不读取**，但其中 `create-subagent` 的思路可参考。

**现状（2026-11-06 已引入 2 个）**：`.agents/skills/` 下现在有 `fastapi`（来自官方 [fastapi/fastapi](https://github.com/fastapi/fastapi) 仓库自带的 `.agents/skills/fastapi/`）与 `vue-best-practices`（来自 ejirocodes/agent-skills），均 MIT、原文保留 + 顶部「本项目适配」段。清单与升级方式见 [docs/agents/README.md §6.1](../agents/README.md)。

**仍缺**：测试（pytest/Playwright）、部署（Docker/Caddy）、Agent 编排（MCP/Agents SDK）、RAG 方向的项目级 Skill。

**补充决策（2026-11-06，项目 owner）**：项目级 Skill **按需从 GitHub 获取开源 Skill**，不自行从零编写。

### 项目级 Skill 目录：DSH 已验证支持（2026-11-06 实测）

结论：**支持，无需重启、无需改 DSH 配置**。

机制（`@deepseek-ai/dsh-skill-filesystem`，随 `dsh-base` 无条件挂载，默认 `includeDefaultRoots: true`）扫描五个根，按 rank 从小到大取优先级：

| rank | 来源 | 路径 | 本项目对应 |
|---|---|---|---|
| 100 | project-dsh | `<项目根>/.dsh/skills` | 仓库根 |
| 200 | project-agents | `<项目根>/.agents/skills` | 仓库根（跨工具共享约定） |
| 300 | custom | `Config.customSkillDirs` | 未配置 |
| 400 | user-dsh | `~/.dsh/skills` | 用户级 |
| 500 | user-agents | `~/.agents/skills` | 用户级（跨工具共享） |

- 项目根 = 含 `.git` 的最近祖先目录（没有则用 cwd）。
- 只识别**根下直接子项**：目录包 `<name>/SKILL.md` 或平铺文件 `<name>.md`；嵌套 `**/SKILL.md` 故意不发现。
- frontmatter 必填 `name`（kebab-case）与 `description`；可选 `whenToUse`、`metadata`、`disable-model-invocation`、`user-invocable`。缺 `description` 的 skill 会被静默跳过（不报错、不进目录）。
- 目录会监视根目录，新增/删除/改名在下一步即生效；正文每次加载重新读取，改正文不必重启。

实测证据（2026-11-06，本仓库，验证后已删除探针文件）：

| 探针 | 结果 |
|---|---|
| `.dsh/skills/probe-skill/SKILL.md` | ✅ 出现在会话目录，`skill` 工具可加载正文 |
| `.dsh/skills/flat-probe.md` | ✅ 平铺形式生效 |
| `.agents/skills/agents-probe/SKILL.md` | ✅ 生效 |
| `.dsh/skills/nested/child/SKILL.md` | ❌ 未被发现（与文档一致） |
| `.dsh/skills/bad-probe/SKILL.md`（缺 description） | ❌ 被跳过，无任何诊断输出 |
| 同名 skill 同时在 `.dsh` 与 `.agents` | 只出现一条，加载 `.dsh` 版本（rank 100 胜 200） |

落地约定（阶段 2 执行）：

1. 项目自研 Skill 放 `.agents/skills/`（跨工具共享，Cursor/Codex 也认这个约定）；仅 DSH 专用、且需要压过同名 `.agents` 版本时才放 `.dsh/skills/`。
2. 只引入**单一职责、说明完整**的 Skill（如 FastAPI 路由规范、Vue SFC 规范），每个都要在 `docs/agents/README.md` 登记来源、版本/commit、引入理由。
3. 引入前先读其完整 `SKILL.md`，确认不会与本项目 `AGENTS.md` 冲突；冲突时以 `AGENTS.md` 为准。
4. 不引入「一键生成整个项目」类重型 Skill——与 AGENTS.md §2.2「小步开发」直接冲突。
5. ⚠️ 本仓库是 **PUBLIC**：写进 `.agents/skills/` 的内容会公开，不要把内部约定、密钥、客户信息放进去。
6. 当前 `.gitignore` 未忽略 `.dsh/`、`.agents/`，即会被提交；`node_modules`/`.venv` 等已在忽略列表内。

## 3. MCP Server 配置

| 位置 | serverName | 传输 | 命令/脚本 | 用途 | 本会话可见 |
|---|---|---|---|---|---|
| DSH profile（`~/.dsh/profiles/web/cordis.patch.yml`） | `snowluma` | stdio | `qq-bridge/src/mcp-snowluma-safe.js` | QQ 群消息收发 | ❌ 工具面未见 `mcp__*` |
| 同上 | `snowluma-host` | stdio | `qq-bridge/src/mcp-host-server.js` | QQ 宿主管理 | ❌ |
| 同上 | `web-search-safe` | stdio | `qq-bridge/src/mcp-web-search-safe.js` | 联网搜索/抓取 | ❌ |
| Codex（`~/.codex/config.toml`） | `node_repl` ×2 | stdio | ChatGPT.app 内置 node REPL | 代码执行 | 与 DSH 无关 |

**事实判断**：配置存在于 profile 层（由 `scripts/setup-dsh.mjs` 维护，注释写明"勿手工编辑内部条目"），但**本会话的工具列表里没有任何 `mcp__*` 工具**——只看到内置的 `web_search` / `web_fetch`。推测是当前 agent preset（`qq-mode`，`mode: reserved2`）未挂载这些 MCP，或它们只对该 preset 生效。**需要你在 GUI 里确认，我没有擅自改动 profile。**

**缺口**：没有任何面向本项目开发的 MCP（数据库查询、浏览器自动化、文件系统/容器管理）。

## 4. CLI 工具矩阵（实测 `--version`）

| 工具 | 版本 | 可用于本项目 | 备注 |
|---|---|---|---|
| git | 2.37.1 (Apple) | ✅ | 较旧，`git switch/restore` 可用 |
| gh | 2.103.3 | ✅ | 已登录 `calix-cui`，token 含 `repo`；**git 未配置凭据助手**，直接 push 会失败 |
| node | v24.21.0 | ✅ | 前端构建/验收脚本 |
| pnpm | 12.10.1 | ✅ | 锁文件已提交；12.x 对 build script 有 allowBuilds 要求 |
| npm | 11.19.0 | ✅ | 仅备用 |
| python3 | 3.15.0 | ⚠️ | 本机 3.15，CI 用 3.12，存在版本漂移 |
| uv | 0.13.4 | ✅ | 建 venv/装依赖很快；注意本机沙箱需 `UV_CACHE_DIR=/tmp/uvcache` |
| docker | CLI 29.9.2 | ❌ 当前不可用 | **守护进程未运行**（`docker info` 连接失败），且**无 `docker compose` 子命令** |
| jq | 1.7.1 | ✅ | 解析 JSON |
| make | GNU Make 3.81 | ✅ | 后端 Makefile 依赖它（3.81 较老，不支持 `.ONESHELL` 之外的少数特性） |
| mysql | 8.4.13 | ✅ | 本机数据库 |
| ruff / pytest / pre-commit | 未装全局 | ✅ 项目内 | 只能 `backend/.venv/bin/python -m ruff` 这样调用；根目录直接跑 `ruff` 会 command not found |
| pipx | 未安装 | — | 装全局 Python CLI 时可用 `uv tool` 替代 |

## 5. 项目中已有的 Agent / Prompt / Rules / Workflow 资产

| 资产 | 位置 | 类型 | 可复用性 |
|---|---|---|---|
| 7 阶段提示词流水线 | `docs/playbooks/1..7` | Prompt | ★★★ 已定义「调研 → 基建 → 架构 → 部署 → 计划 → 单任务 → 评审」的完整链路，是当前最有价值的 AI 资产 |
| 开发全局规范 | `AGENTS.md` | Rule | ★★★ 但未提交 |
| 提交前检查链 | `.pre-commit-config.yaml` | Workflow | ★★ 仅后端 |
| CI 流水线 | `.github/workflows/ci.yml` | Workflow | ★★ 仅后端 |
| 后端一键命令 | `backend/Makefile` | Workflow | ★★ |
| UI 验收脚本 | `frontend/scripts/acceptance.mjs` | Workflow | ★★★ 18 项断言 + 截图，可直接演进为回归基线 |
| 多角色协作实践 | 上一轮任务的 4 个 teammate（产品/设计/后端/前端） | Agent（会话内，已结束） | 经验在，**定义未落盘**（本阶段补 `docs/agents/`） |
| DSH 插件商店 | `search-dsh-store` Skill + `store_*` 工具 | 能力 | ★★ 装插件/技能时用 |

**未发现**：项目内自定义 subagent 定义、任务板模板、ADR 目录、规格驱动（spec-driven）工作流。

## 6. 可复用的 AI 开发工作流（现在就能用）

1. **分阶段提示词**：`docs/playbooks/N` 直接作为每次任务的输入，产出物按提示词末尾"交付文档"落盘。
2. **子智能体并行**：调研/审计类任务用 `subagent`（fresh context，不污染主会话）；需要继承上下文的评审用 `subagent_fork`。
3. **多角色协作**：需要 3 人以上并行且互相等结果时，用任务板 + `spawn_teammate`（上一轮已验证可行）。
4. **验收脚本当回归**：`pnpm acceptance` 已是可执行规格，改前端后先跑它。

## 7. 缺失能力与建议（按优先级）

| 优先级 | 缺失 | 建议 | 详见 |
|---|---|---|---|
| P0 | `AGENTS.md` / `docs/prompts` 未入库 | 先提交，避免规则丢失 | `TECHNICAL_DEBT.md` T-01 |
| P0 | 前端零静态检查、零单测、零 CI | ESLint + Vitest，并把 `pnpm build` 加进 CI | `TECHNICAL_DEBT.md` T-03 |
| P1 | 无部署能力（Docker/compose/反代/健康检查） | 阶段 4 统一做 | `REUSE_CANDIDATES.md` |
| P1 | 数据库无迁移 | 引入 Alembic | 同上 |
| P1 | 子智能体角色未落盘 | 本阶段补 `docs/agents/` | 已随本次调研完成 |
| P2 | 无项目级 Skill | 等架构定型后，把"新增一个 CRUD 资源""跑验收"做成 Skill | 同上 |
| P2 | MCP 不可用 | 在 GUI 确认 qq-mode 是否屏蔽；按需加 DB/浏览器 MCP | `AI_ENVIRONMENT_AUDIT.md` §3 |

## 8. 风险提示

1. **仓库是 Public**：`.env` 从未入库（已核对提交历史），但任何新增文件都要过一遍密钥扫描（pre-commit 已含 `detect-private-key`）。
2. **Python 3.15 vs CI 3.12**：本机能跑不代表 CI 能跑，反之亦然；建议加 `.python-version` 并统一。
3. **Docker 不可用**：阶段 4 若要做容器化，需要先装 Docker Desktop 或改用 `colima`/`podman`（届时再评估）。
4. **`gh` 凭据未接 git**：上次 push 是靠临时 `-c credential.helper='!gh auth git-credential'` 绕过的，建议 `gh auth setup-git` 固化（需你同意改全局配置）。
5. **`cordis.patch.yml` 由脚本维护**：里面的 MCP 区块不要手改，否则会被 `setup-dsh.mjs` 覆盖。
