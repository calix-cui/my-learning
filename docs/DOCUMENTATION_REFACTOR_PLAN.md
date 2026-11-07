# 文档体系重构方案

> **阶段二产物，仅方案**：本文不改动任何既有文档。
> 依据：`docs/DOCUMENTATION_AUDIT.md`（阶段一）· 基线 `main` @ `8a3e806`
> 需要你确认后才能进入阶段三；确认项集中在 §9。

---

## 1. 设计原则（本次重构的取舍）

| 原则 | 具体落地 |
|---|---|
| 结构已经对了，不再换目录 | 保留「人读平铺在 `docs/`、AI 向收在 `docs/{adr,agents,prompts}/`」的三层结构，只做局部归位 |
| **不新增人读文档** | 缺失内容全部作为**已有文档的章节**补齐（新增资源路径 → `how-it-works`；测试全景 → `toolchain`；环境变量总表 → `deploy`），只有两份治理报告是新增 |
| 命令与端口允许短重复，事实类信息必须唯一 | 见 §5 单一事实来源表 |
| 数字只在「权威文件」里出现一次，其他文档用链接或占位 | 单测数、覆盖率、接口数、验收条数全部收敛到 3 个文件 |
| 归档不动 | `docs/archive/*` 只补「结论已迁至 ADR-xxxx」索引行 |
| 上游 Skill 不动 | `.agents/skills/**` 保持原文 + `SOURCE.md` |
| 一次一批、每批可独立回滚 | 见 §7 |

**目标规模**：39 文件 / 4089 行 → **36 文件 / 约 2900 行**（−29%），文件减少 3 个（删 `app/README.md`、合并 2 处重复章节），不新增人读文档。

---

## 2. 目标目录树

```
my-learning/
├── README.md                     89 → 95   项目门面：是什么、怎么跑、去哪看
├── AGENTS.md                    219 → 245  AI 全局规则（+现状定位、+文档路由表）
├── CONTRIBUTING.md               57 → 45   贡献流程（文档约定降为一段 + 链接）
├── .agents/skills/**           2948（不动）
└── docs/
    ├── README.md                 80 → 105  导航：三条阅读路径 + 文档地图（+4 行）+ 单一事实来源
    ├── how-it-works.md          137 → 185  架构：架构图/时序图/数据模型/分层职责/+新增资源路径
    ├── toolchain.md             121 → 150  工具链：四张图 + 工具表 + /+测试全景
    ├── api.md                     0 → 285  ← 从 python/fastapi-demo/docs/api.md 迁入（待确认 Q1）
    ├── deploy.md                 99 → 125  部署：+环境变量总表 +Caddy 未实测标注
    ├── delivery.md              119 → 125  验收：数字校准 + 图片引用 + 偏差记录
    ├── PROJECT_STATUS.md         81 → 85   进度：唯一「现在到哪了」
    ├── TECHNICAL_DEBT.md        191 → 165  债务：状态位重写、关闭 5 条、补新债
    ├── product/
    │   └── prd.md               199 → 185  需求：唯一「要什么」
    ├── design/
    │   ├── design.md            162 → 155  设计规范：唯一「长什么样」
    │   ├── images/design-*.png    5 张    ← 由 01..05-*.png 改名
    │   └── mockups/*.html         5 个    保留，纳入索引
    ├── images/
    │   ├── shot-*.png             5 张    ← 实机截图，由 01..05-*.png 改名
    │   └── diagram-*.png         5 张    保留，补「由哪个 md 渲染」说明
    ├── adr/                     297（不动）  决策记录 5 篇 + 索引
    ├── agents/                  475 → 460  角色卡（数字与触发条件校准）
    ├── prompts/                 679（不动，补入口）  阶段 1–7 提示词
    └── archive/                 480（不动，补 3 行索引）

python/fastapi-demo/
├── README.md                    177 → 150  后端手册（接口一览改为链接）
├── docs/api.md                  278 → 迁出（见 §4）
└── app/README.md                  9 → 删除（待确认 Q2）

fullstack/product-admin/
└── README.md                    140 → 125  前端手册（页面说明降级为路由表）
```

目录最深仍是 3 层（`docs/design/images/`），不新增层级。

---

## 3. 每份文档的职责、边界与独立存在理由

> 「独立理由」= 它是否拥有**独立的读者、维护责任或查阅场景**；不满足的合并或降级为章节。

| 文档 | 一句话职责 | 负责 | 明确不负责 | 独立存在理由 |
|---|---|---|---|---|
| `README.md` | 项目门面与 15 秒判断 | 定位、状态、两条启动路径、目录、文档入口 | 技术设计、命令全集 | 新访客第一落点 |
| `AGENTS.md` | AI 在本仓的硬规则 | 开发原则、质量红线、行为流程、**文档路由** | 项目知识百科、具体任务步骤 | AI 每次会话必读，必须短而稳 |
| `CONTRIBUTING.md` | 贡献者怎么提交 | 新增项目/依赖/提交/评审要求 | 文档分层细节（链到 docs/README） | 面向人，面向 PR 流程 |
| `docs/README.md` | 文档导航与治理规则 | 阅读路径、文档地图、三层结构、SSOT 表 | 任何项目事实的具体内容 | 唯一入口，防止孤儿 |
| `how-it-works.md` | 系统怎么跑起来 | 架构图、时序图、数据模型、分层职责、代码地图、**新增资源路径** | 需求、部署细节、工具配置 | 「我要改代码」的第一站 |
| `toolchain.md` | 每个工具为什么在、怎么用 | 四张链路图、工具表、CI、**测试全景** | 业务规则、部署运维 | 工程化问题的高频落点 |
| `api.md` | 前后端唯一契约 | 通用约定、11 个业务操作、错误码、示例 | 业务为什么这么设计（PRD） | 前后端同时读，必须唯一 |
| `deploy.md` | 怎么跑在容器/服务器上 | 前置、启动、端口、健康检查、**环境变量表**、备份、排障 | 本地开发流程 | 运维/复现问题 |
| `delivery.md` | 交付证据与验收记录 | 结论、复跑方式、18 项用例、D/L 记录 | 需求定义、设计规范 | 历史证据，一次性但需可查 |
| `PROJECT_STATUS.md` | 现在到哪了 | 阶段、已完成、下一步、决策索引、已知问题、阻塞 | 长期方案（→ ADR） | 每次任务开始前的唯一进度源 |
| `TECHNICAL_DEBT.md` | 尚未做的技术事项 | T-xx 清单、优先级、成本、证据 | 已解决的细节（关闭后一句话） | 排期输入 |
| `product/prd.md` | 要做什么、怎么算做完 | 角色、页面、F/AC/Q/N 表、字段、校验 | 实现方式、技术选型 | 产品与验收依据 |
| `design/design.md` | 长什么样 | Token、组件规格、页面规格、稿索引 | 需求定义、实现代码 | 前端与设计对齐 |
| `adr/*` | 为什么这么选 | 决策、理由、代价、被否方案、复评触发 | 现状描述（现状在 STATUS） | 决策可追溯，历史不改 |
| `agents/*` | 角色怎么协作 | 角色边界、写作用域、验收命令、交付格式 | 项目事实（链接权威源） | 多智能体协作协议 |
| `prompts/*` | 分阶段任务提示词 | 每个阶段的操作步骤 | 项目状态 | 可复用的阶段入口 |
| 后端 `README.md` | 后端怎么开发 | 技术栈、目录、本地命令、迁移、测试 | 接口字段（→ api.md） | 单独在后端目录工作时 |
| 前端 `README.md` | 前端怎么开发 | 技术栈、命令、门禁、联调、路由表、限制 | 设计规格（→ design）、需求（→ prd） | 单独在前端目录工作时 |

---

## 4. 现有 → 目标映射与操作清单

### 4.1 迁移（路径变化）

| 从 | 到 | 理由 | 连带工作 |
|---|---|---|---|
| `python/fastapi-demo/docs/api.md` | `docs/api.md` | 契约是前后端共用，现在要 `../python/fastapi-demo/docs/api.md` 三段跳；且它在 `docs/README.md` 地图里已被当作 `docs/` 文档登记 | 重写 7 处引用；后端 README 改为链接；`git mv` 保留历史 |
| `docs/design/images/01..05-*.png` | `docs/design/images/design-01..05-*.png` | 与 `docs/images/` 同名不同源（T-20），且 04/05 内容互换 | 改 `design.md` 5 行图片路径 |
| `docs/images/01..05-*.png` | `docs/images/shot-01..05-*.png` | 同上 | 改 `delivery.md` 图片引用 |

### 4.2 删除（内容不丢）

| 文件 | 内容去向 |
|---|---|
| `python/fastapi-demo/app/README.md`（9 行） | 7 行目录职责并入 `how-it-works.md` §3 代码地图表（该表已有相同信息，实际只需补 2 个包注释） |

### 4.3 合并且不丢信息

| 合并对象 | 结果 |
|---|---|
| `CONTRIBUTING.md` §文档约定（4 段） | 压缩为 1 段 + 指向 `docs/README.md` §3–§5；`package-lock.json` 例子改 `pnpm-lock.yaml` |
| 后端 README「接口一览」12 行表 | 改为 3 行汇总（6 个商品操作 / 5 个分类操作 / 3 个运维探针）+ 链接 `docs/api.md` |
| 前端 README「页面说明」表 | 降级为「路由 → 组件」5 行表，行为说明留给 PRD/design |
| `docs/README.md` §4 与 PROJECT_STATUS「关键决策」表 | PROJECT_STATUS 只留 1 行「决策见 `adr/README.md`」+ 3 条最影响当下的事实 |

### 4.4 更新（内容纠错，不增结构）

全部 A 类 22 条（见审计报告 §4.1）逐条修，按文件聚合：

| 文件 | 要改的条目 |
|---|---|
| `README.md` | A-01（55/85.38）、加一行指向 `docs/api.md` |
| `docs/delivery.md` | A-02、图片引用改 `shot-*`、补 X-01 偏差（整表单提交）|
| `docs/PROJECT_STATUS.md` | A-03、A-07（11 接口）、决策表降为 3 行 + 链接 |
| `python/fastapi-demo/README.md` | A-04、A-05、B-04（接口表→链接）|
| `docs/api.md` | A-06（11 业务操作 / 14 operation）|
| `docs/README.md` | A-07、A-08（第 7 节）、A-09…A-13 对应行、B-01 |
| `CONTRIBUTING.md` | A-08、A-21、B-01 |
| `docs/TECHNICAL_DEBT.md` | A-09…A-13 关闭、T-04/T-19 更新、删「无 ADR」、基线日期 |
| `docs/product/prd.md` | A-22（AC 用 N）、A-06 关联（A-01…A-11 加「路径见 api.md」）|
| `docs/design/design.md` | A-14、A-15 |
| `fullstack/product-admin/README.md` | A-16、A-17、A-18、B-05（页面表降级）|
| `docs/agents/python-backend-dev.md` | A-19 |
| `docs/agents/README.md` | A-20（QA/DevOps 触发条件改为「已有 Vitest / 已有容器化」）|

### 4.5 补缺（章节级新增，不建新文件）

| 缺口 | 落在哪 | 规模 |
|---|---|---|
| C-01 新增一个资源的端到端路径 | `docs/how-it-works.md` 新增 §7「新增一个资源要动哪些文件」（表 → 模型 → 迁移 → schema → service → api → 测试 → 文档） | +45 行 |
| C-04 测试全景 | `docs/toolchain.md` 新增 §5「测试全景」（接口层/服务层/前端单测/18 项 E2E 各覆盖什么、不覆盖什么、什么时候补哪个） | +25 行 |
| C-02 环境变量总表 | `docs/deploy.md` 新增 §3.1（后端 `DATABASE_URL`；compose 的 `MYSQL_ROOT_PASSWORD`/`MYSQL_DATABASE`/`MYSQL_USER`/`MYSQL_PASSWORD`/`FRONTEND_PORT`/`HTTP_PORT`/`HTTPS_PORT`/`SITE_ADDRESS`，含默认值与是否必填） | +20 行 |
| C-03 AI 文档路由 | `AGENTS.md` 新增 §9「遇到什么任务读哪些文件」（8 行表） | +18 行 |
| C-05 阶段路线图 | `PROJECT_STATUS.md` §3 扩为「阶段 1 已完成 / 阶段 2 进行中（含 3 个门槛）」 | +12 行 |
| C-06 地图补漏 | `docs/README.md` §2 增 4 行：`TECHNICAL_DEBT.md`、`prompts/`、`design/mockups/`、`images/` | +4 行 |

### 4.6 AGENTS.md 的定位修正（X-07）

- 新增 **§0 当前阶段与交付物**（6 行）：说明长期目标是 Agent 应用，**当前实际交付**是商品管理后台 + 后端 API，避免新会话按「Agent 项目」预设立场写代码；链接 `README.md` 与 `PROJECT_STATUS.md`。
- 新增 **§9 文档路由表**：任务类型 → 必读文件（改接口 → `docs/api.md` + `how-it-works`；改样式 → `design.md`；改表结构 → 后端 README 迁移节 + ADR-0003；发版/部署 → `deploy.md`；改门禁 → ADR-0002/0005 + `toolchain.md`；写新功能 → `prd.md` + `how-it-works` §7）。
- 保留原有 8 节原则不动（它们是对的，且是「约束」不是「知识」）。

---

## 5. 单一事实来源（SSOT）设计

| 事实 | 权威来源 | 其他位置允许的形态 |
|---|---|---|
| 接口路径 / 请求体 / 错误码 | `docs/api.md` | 其他文档只写「见 api.md」或一句概述 |
| 单测数量 / 覆盖率 / 覆盖率门槛 | `docs/PROJECT_STATUS.md`（结论）+ `pyproject.toml`（配置） | `delivery.md` 写一次结论；README 只写「有 55 个单测」不写百分比 |
| 验收条数与结果 | `docs/delivery.md` | `PROJECT_STATUS` 一行、前端 README 一行 |
| 端口与地址 | `docs/deploy.md` §3 端口表 | 各 README 只提自己那一个端口，不列全表 |
| 环境变量 | `docs/deploy.md` §3.1 | `.env.example`（机器可读）+ 一句链接 |
| 本地命令全集 | `docs/toolchain.md` §7 速查表 + `Makefile`/`package.json` | README 只列 5 条最常用 |
| 目录职责 | `docs/how-it-works.md` §3 | 各 README 只列自己的子目录 |
| 页面/功能清单 | `docs/product/prd.md` | design 写「规格」，前端 README 写「路由」 |
| 设计 Token | `docs/design/design.md` §2 | 前端 README 不写色值 |
| 架构决策 | `docs/adr/*` | 其他文档只引用编号 |
| 进度与阻塞 | `docs/PROJECT_STATUS.md` | 其他文档不重复进度 |
| 技术债 | `docs/TECHNICAL_DEBT.md` | 其他文档引用 `T-xx` |
| 文档治理规则 | `docs/README.md` §3–§5 | `CONTRIBUTING.md` 一段 + 链接 |
| 项目定位 | `README.md` §1 | `AGENTS.md` §0 引用一句话 + 链接 |

> 配套校验（可选，Q6）：`scripts/check-docs.mjs`（Node 内置 `fs`，零依赖，约 60 行）做三件事——①相对链接存在性；②禁用词扫描（`85.12`、`12 个业务`、`50 passed` 等已废弃数字出现在非权威文件即报错）；③地图完整性（`docs/**/*.md` 必须出现在 `docs/README.md` §2）。CI 里只对 `docs/**` 与 `README.md` 的改动触发。

---

## 6. 导航与引用关系

### 6.1 人读路径（与 `docs/README.md` 三条路径一致）

```
新访客   README → docs/README（10 分钟路径）→ how-it-works
开发     docs/README（40 分钟路径）→ how-it-works → toolchain → 对应 README
改功能   prd（为什么）→ how-it-works §7（改哪些文件）→ api.md（契约）→ 代码
查运维   deploy → 环境变量表 → 排障
```

### 6.2 AI 路由（写入 AGENTS.md §9）

| 任务 | 必读 | 可选 |
|---|---|---|
| 改后端接口/校验 | `docs/api.md`、`how-it-works.md` §3–§4、后端 README 测试节 | `prd.md` 对应 F/AC |
| 改前端页面/样式 | `design.md`、前端 README、`docs/api.md` | `prd.md` 对应 F |
| 改表结构 | 后端 README「数据库迁移」、ADR-0003 | `how-it-works.md` §5 数据模型 |
| 改工程化/门禁 | ADR-0002、ADR-0005、`toolchain.md` | agent 角色卡 |
| 部署/排障 | `deploy.md`、ADR-0004 | 根 README 快速开始 |
| 写新功能 | `prd.md`、`how-it-works.md` §7、`PROJECT_STATUS.md` §3 | 相关 ADR |

### 6.3 引用方向约束（防循环）

- 允许：`README → docs/README → 任意`；`PROJECT_STATUS → ADR/DEBT`；`delivery → api/design`；`prd ↔ design`（互链但各自定义）。
- 禁止：`how-it-works` 反向引用 `delivery`；`api.md` 引用 `prd.md`（契约不依赖需求文档）；两份文档互相定义同一事实。

---

## 7. 分批执行顺序

> 每批结束都执行：链接检查 → 地图核对 → 关键数字 grep 一致性 → 行数统计 → 汇报。文档改动不触发 CI（`ci.yml` 的 `paths` 只含 `python/**`、`fullstack/**`、自身）。

### 批 1：入口与事实校准（8 文件，预计 -60 行）

| 文件 | 动作 |
|---|---|
| `docs/TECHNICAL_DEBT.md` | 关闭 T-01/T-03/T-12/T-13、更新 T-04/T-19、删「无 ADR」行、更新基线日期与统计 |
| `docs/PROJECT_STATUS.md` | 数字校准、决策表收敛、阶段路线图扩写 |
| `README.md` | 数字校准、加 api.md 链接 |
| `docs/README.md` | 修 A-07/A-08、地图 +4 行、SSOT 表更新 |
| `AGENTS.md` | §0 现状、§9 路由表 |
| `CONTRIBUTING.md` | 文档约定压缩、`package-lock.json` → `pnpm-lock.yaml` |
| `docs/delivery.md` | 数字、图片引用、X-01 偏差 |
| `docs/product/prd.md` | AC 用 N、接口路径指向 api.md |

**验收**：`grep -r "85.12\|50 passed\|12 个业务" ` 只应命中 `docs/archive/`；`grep -c "第 8 节"` = 0。

### 批 2：专业文档纠错与补缺（9 文件，预计 +110 行）

| 文件 | 动作 |
|---|---|
| `docs/how-it-works.md` | +§7 新增资源路径（+45） |
| `docs/toolchain.md` | +§5 测试全景（+25） |
| `docs/deploy.md` | +§3.1 环境变量表（+20）、Caddy 未实测标注 |
| `docs/api.md` | 迁入 `docs/` + 11/14 修正；7 处引用重写 |
| `python/fastapi-demo/README.md` | 接口表降级为链接、删「没有 Docker」、55 |
| `fullstack/product-admin/README.md` | decimal、启动命令、响应式、页面表降级 |
| `docs/design/design.md` | 图片改名、稿内数据说明 |
| `docs/agents/README.md`、`python-backend-dev.md` | 触发条件与数字 |
| `python/fastapi-demo/app/README.md` | 删除；2 条注释并入 `how-it-works` §3 |

**验收**：`make check`（55/85.38）、`pnpm lint && pnpm test`（17）、mermaid 6 张全部可渲染、`sha256` 无变化的代码文件。

### 批 3：资产与索引收尾（5 文件 + 图形资产）

| 动作 | 说明 |
|---|---|
| 图片改名 `design-*` / `shot-*` | 用 `git mv` 保历史；同步改 `design.md`、`delivery.md` |
| `docs/archive/README.md` | 补 3 行「结论已迁至 ADR-0001/0002/0005」 |
| `docs/images/diagram-*.png` | 在 how-it-works/toolchain 各加一行「由本文件 §X 的 mermaid 渲染」 |
| `docs/prompts/` | 登记进地图（不移动，见 Q5） |
| `scripts/check-docs.mjs`（可选） | 链接 + 禁用数字 + 地图完整性三合一校验 |

**验收**：全仓链接 0 失效、地图覆盖 100%、`git status` 无意外文件。

### 批 4：终检报告

输出 `docs/DOCUMENTATION_FINAL_REPORT.md`（按任务书阶段四要求：目录树、职责、变更清单、成果、链接检查、待确认、维护建议）。

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 迁移 `api.md` 断 7 处引用 | 链接失效 | 迁移与引用重写同一提交；批 2 用脚本校验 |
| 图片改名断 `design.md` 与归档引用 | 图裂 | 同批改名 + 同批改引用；`check-docs` 兜底 |
| 数字统一后仍有遗漏（如 agents 卡片里的 23 passed） | 口径再次分叉 | 批 1 用 `grep -rn "85\.12\|50 passed\|23 passed\|12 个业务\|第 8 节"` 全仓扫，命中即改 |
| 删除 `app/README.md` 后有人习惯性找它 | 轻微 | 在 `how-it-works.md` §3 顶部加一行「原 `app/README.md` 内容已并入本节」 |
| 补 §7「新增资源路径」写成通用模板但与本项目不符 | 误导 | 用当前真实链路写（categories 的 7 步），不写抽象模板 |
| 归档文档里的旧结论与 ADR 冲突 | 读者混淆 | 归档 README 标注「结论已迁至 ADR-xxxx，本文件不再维护」 |
| 过度精简导致上下文丢失 | 信息损失 | 只删「重复副本」与「空话」，不删决策理由、约束、排障记录；每批后 diff 逐条核对 |

---

## 9. 需要你确认的 6 件事

| 编号 | 问题 | 我的建议 | 不确认的默认动作 |
|---|---|---|---|
| Q1 | `python/fastapi-demo/docs/api.md` 迁到 `docs/api.md`？ | **迁**（导航短、与「前后端契约」定位一致，成本 7 处引用） | 不迁，只在 `docs/README.md` 地图里保留原路径 |
| Q2 | 删除 9 行的 `python/fastapi-demo/app/README.md`？ | **删**（内容与 how-it-works §3、后端 README 目录树三重重叠） | 保留，但改为 3 行纯链接文件 |
| Q3 | PRD 的 AC 数字（写死 12 条）改为「以实际 total 为准」？ | **改**（否则换台机器验收就红） | 保留 12 条，另加一句「示例数据」 |
| Q4 | 两套同名图片命名 `design-*` / `shot-*`？ | **改**（当前 04/05 内容互换，极易看错） | 不改，仅在两处 README 说明区别 |
| Q5 | `docs/prompts/` 留在 `docs/` 顶层，还是移到 `docs/agents/prompts/`？ | **留顶层**（它是「阶段任务入口」，与角色卡不同类；移动会打断 `docs/prompts/1. Know the project.md` 这类已被引用的路径） | 留顶层并登记进地图 |
| Q6 | 是否在 CI 增加零依赖的 `scripts/check-docs.mjs`（链接 + 废弃数字 + 地图完整性）？ | **加**（约 60 行，纯 Node 内置模块，不引入依赖） | 只本地保留脚本，不接 CI |

另需确认 2 条记录型冲突（不阻塞，但影响后续验收口径）：
- **X-01**：PRD AC-08 要求「编辑只提交 `stock`」，前端实现为整表单提交 —— 记为已知偏差，还是要求前端改成局部 PATCH？
- **X-02**：`deploy.md` 的 Caddy/HTTPS 段未实测 —— 记为「未验证」标注，还是本轮补一次 `--profile https` 实测？

---

## 10. 执行边界（承诺）

- 不改 `.py` / `.ts` / `.vue` / SQL / `Dockerfile` / `compose` / `Makefile` / `pyproject.toml`（唯一例外：若 Q6 通过，新增 `scripts/check-docs.mjs`）。
- 不装任何依赖。
- 删除只发生在 Q2 确认的 1 个 9 行文件；其余为「内容合并后删除副本」，且删除前把内容并入目标文档并在提交信息里注明。
- 每批一个提交，提交信息形如 `docs: 校准文档事实与补齐导航（批 1）`，便于逐批回滚。
- 阶段三开始前，等你对 §9 的答复。
