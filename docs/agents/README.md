# docs/agents — 子智能体角色卡与协作协议

> **AI 向文档**：给 AI 协作者的作业指导书。人类读者可跳过——阅读路径见 [`docs/README.md`](../README.md)。

> 目的：把「每个角色该做什么、不该做什么、交付什么、怎么验收」从对话里固化下来。
> 上一次协作（商品管理网站，7 个提交）暴露的核心问题是：**角色边界靠临时提示词**，同一角色在不同任务里的输出质量不稳定。
> 本目录把有效提示词沉淀成可复用角色卡，`spawn_teammate` 时直接引用。

## 1. 怎么用

1. **派活前**：读目标角色的角色卡，把它作为 `spawn_teammate` 的 `prompt` 主体（替换其中的 `<任务单>`、`<写作用域>` 占位）。
2. **角色卡 + 任务单分开**：角色卡是长期不变的能力边界；任务单是本次的一次性输入（目标、验收标准、写作用域）。
3. **完成后**：让子智能体 `send_message` 给 lead 汇报（模板见每张卡的「交付模板」），并 `team_task_update` 标记 complete。**不要只改文件不回话**。

## 2. 当前角色

| 角色 | target | 定位 | 写作用域 | 是否常设 |
|---|---|---|---|---|
| 产品经理 | `product-manager` | 需求 → PRD + 验收标准 | `docs/product/` | 常设 |
| UI 设计师 | `ui-designer` | PRD → 设计规范 + 设计稿 + 截图 | `docs/design/` | 常设 |
| Python 后端 | `python-backend-dev` | 接口/数据/契约 | `python/fastapi-demo/` | 常设 |
| Vue 前端 | `vue-frontend-dev` | 管理后台实现 | `fullstack/product-admin/` | 常设 |
| 技术调研 | `tech-researcher`（新增） | 选型/方案调研，不写业务代码 | `<任务指定的 docs 目录>` | 按需派生 |

**不常设的角色**（有需求再建，现状是不需要）：
- **QA / 测试工程师**：当前验收（18 项 E2E + 接口抽查）由 lead 兼任，量还不够拆角色。触发条件：后端有了集成测试套件、前端有了 Vitest 套件，需要人长期维护回归时再建。
- **DevOps**：容器化/CI/CD 尚未开始（见 `docs/TECHNICAL_DEBT.md` T-09），阶段 4 再建。
- **架构师**：架构决策由 lead 直接做并写 ADR，避免「架构师定方案、leader 背锅」的权责错位。

## 3. 协作协议（写进每个任务单）

### 3.1 任务板是唯一事实源
- 一个可交付物 = 一个 `team_task_*`，create 时写清：目标、前置条件、实施步骤、涉及文件、验收标准。
- 子智能体开工先 `team_task_list` 找自己的任务，`claim` 后再动手；结束 `complete` 并附一句「实际验证结果」。
- 依赖用 `blocked_by` 表达（设计稿完成后才排前端实现），不要用「等我叫你」的隐性等待。

### 3.2 写作用域互不重叠
每个任务声明 `write_scopes`。**跨作用域的修改一律回报 lead，由 lead 决定谁改**。上一次的教训：前端为了修概览版式直接改了 `src/styles/index.css` 里公共 `.stat-card`——这是允许的（同作用域内），但若跨到后端就必须先问。

### 3.3 完成 = 可验证
- 后端：`make check` 全绿 + 关键接口 curl 实测（贴请求与响应）。
- 前端：`pnpm build` 通过 + 至少一张实机截图（1440×900）+ 关键交互实测。
- 设计：5 页 PNG 全部 2880×1800（@2x）+ HTML mockup 可离线打开。
- 产品：每条 AC 都是「Given/When/Then」且能被测试/人工验证，不许写「体验良好」。

### 3.4 阻塞就升级，不要空转
遇到「需要改冻结代码 / 需要装依赖 / 与 PRD 冲突 / 无法验证」时，立刻 `send_message` 给 lead 说明三件事：卡在哪、需要什么、你建议怎么做。**禁止猜着做、禁止改完再解释**。

### 3.5 端口与数据约定
| 用途 | 地址 | 备注 |
|---|---|---|
| 后端（开发） | `127.0.0.1:8000` | `make run` |
| 前端 dev | `127.0.0.1:5173` | 代理 `/api` → 8000 |
| 后端（验证用第二实例） | `127.0.0.1:8020` | 避免和 lead 的 8000 抢端口 |
| MySQL | `127.0.0.1:3306`，库 `fastapi_demo` | 本机 root |

**数据纪律**：任何自动化脚本（E2E/验收）创建的数据必须带唯一前缀并在结束时清理。已经有教训——验收脚本误删过一台真实商品。

## 4. fresh 还是 fork

| 场景 | 选择 | 原因 |
|---|---|---|
| 角色第一次派活、任务自包含 | `fresh` | 上下文干净，不会被历史决策干扰 |
| 需要沿用上一次的产出细节（如「接着上次的 PRD 改」） | `fork` | 继承已验证的上下文，省重复阅读 |
| 任务需要读大量仓库代码 | `fresh` + 明确文件清单 | 比 fork 整个对话便宜 |
| 长任务中途换人 | `fork` | 避免丢失进行中的判断 |

**默认 fresh**：角色卡 + 任务单已经足够自包含，fork 会把上一轮的无关细节带进来。

## 5. 角色卡清单

- [product-manager](./product-manager.md) — 需求拆解、PRD、验收标准
- [ui-designer](./ui-designer.md) — 设计规范、设计稿、实现核对
- [python-backend-dev](./python-backend-dev.md) — FastAPI 接口、数据模型、契约
- [vue-frontend-dev](./vue-frontend-dev.md) — Vue3 + TS 管理后台
- [tech-researcher](./tech-researcher.md) — 技术选型与可行性调研（新增）

## 6. 技术决策的出处

角色卡只写「怎么做」，不重新论证「为什么这么选」。技术选型以 [docs/adr/](../adr/README.md) 为准：

- 桌面端外壳 = Electron（[ADR-0001](../adr/0001-desktop-shell-electron.md)）→ 未来 `desktop/` 相关任务按此执行，不要重新推荐 Tauri。
- 前端门禁 = 轻量档（[ADR-0002](../adr/0002-frontend-quality-gate-lite.md)）→ vue-frontend-dev 不要自行加严。

## 6.1 项目级 Skill 清单

技术类 Skill 放在仓库内 `.agents/skills/`，DSH 会在会话目录里自动发现（机制已验证，见 [AI_ENVIRONMENT_AUDIT §2](../archive/AI_ENVIRONMENT_AUDIT.md)）。**引入/升级任何 Skill 都要更新下表。**

| Skill | 上游 | 引入 commit | 许可 | 本地修改 | 用途 |
|---|---|---|---|---|---|
| `fastapi` | [fastapi/fastapi](https://github.com/fastapi/fastapi) `fastapi/.agents/skills/fastapi/` | `1ca09c1` | MIT | frontmatter 后插入「本项目适配」段 | 官方 FastAPI 约定：`Annotated`、不用 `...`、return type/`response_model`、router 级 prefix/tags、`def` 优先 |
| `vue-best-practices` | [ejirocodes/agent-skills](https://github.com/ejirocodes/agent-skills) `vue/skills/vue-best-practices/` | `6e805e4` | MIT | 同上（声明技术栈与「新依赖先说明」） | Vue 3.5 + TS 事实与坑：props 提取、`defineModel`、Volar/`vue-tsc`、Pinia 测试 |

规则：

1. 只引**单一职责**、有明确上游维护者的 Skill；不引「一键生成整个项目」类。
2. 与项目约定冲突时，在 `SKILL.md` frontmatter 之后加「本项目适配」段（保留上游原文，便于 diff 升级），不要删改原文。
3. 每个 Skill 目录必须有 `SOURCE.md`（来源、commit、日期、本地修改说明）与 `LICENSE`。
4. 仓库是 PUBLIC：Skill 内容会公开，不得写入内部约定、密钥、客户信息。

## 7. 与 DSH 自身机制的关系

本目录的「子智能体」= 会话内的 **teammate**（`spawn_teammate` 派生，durable，有任务板与互相通信）。
DSH 另有一套 GUI 级 **agent preset** 机制（`@deepseek-ai/dsh-agent-preset`，当前 web profile 里挂了 QQ 聊天用的 `qq-chat-v2`）。给本项目做专用 preset 需要改 profile 配置、需要重启与审批，且当前单人会话下没有收益——**暂不配置**，等出现「同一角色要被反复复用、且希望一键切换」的需求再说。
