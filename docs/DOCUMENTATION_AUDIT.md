# 文档体系审查报告

> **阶段一产物，只读审查**：本次没有修改、移动、重命名或删除任何既有文件。
> 审查基线：`main` @ `8a3e806`（工作区干净）· 审查时间：2026-11-07
> 审查范围：仓库内全部 Markdown（含代码目录内文档、AI 协作配置、Skill），共 54 个文件 / 7037 行。

---

## 0. 结论摘要

1. **文档总量偏大但并不臃肿**：剔除上游 Skill 正文后是 39 个文件 / 4089 行；问题不在「多」，而在**同类事实被写了 2–10 遍**（`make check` 出现在 10 个文件、`18 项验收` 出现在 9 个文件、`127.0.0.1:8000` 出现在 8 个文件）。
2. **最严重的问题是「过期而非缺失」**：迭代很快（uv / Alembic / Docker / 前端门禁 / 测试基线都是 11-07 一天内落地），导致 6 份文档停在旧状态。典型：`docs/TECHNICAL_DEBT.md` 仍把「无 ADR」「AGENTS.md 未入库」「前端零单测」「gh 凭据未接」列为待办（§8 第 184 行、T-01、T-03、T-13），而它们都已解决。
3. **数字口径已经分叉**：同一份仓库里同时存在「50 个单测 / 85.12%」与「55 passed / 85.38%」两套数字，出现在 README、delivery、PROJECT_STATUS 三个文件。
4. **接口数量写错一处、扩散到三处**：真实是 **11 个业务操作 + 3 个运维路径 = 14 个 operation**（`app.openapi()` 实测），但 `python/fastapi-demo/docs/api.md:8`、`docs/README.md:40`、`docs/PROJECT_STATUS.md:12` 都写「12 个业务接口」，而 PRD 写的是 11 —— 三个数字并存。
5. **导航层有孤儿**：`docs/prompts/` 下 7 个文件（阶段 1–7 提示词）没有被任何文档引用，也不在 `docs/README.md` 的文档地图里。
6. **AI 协作路由薄弱**：`AGENTS.md`（219 行）只在一处提到 `docs/README.md`、一处提到 `PROJECT_STATUS.md`，没告诉 AI「改接口该读哪份、改样式该读哪份」；同时它开篇把仓库定位成「AI Agent 应用开发项目」，而当前实际交付是商品管理后台——定位与现状脱节。
7. **职责边界有两处明显重叠**：`CONTRIBUTING.md` 的「文档约定」与 `docs/README.md` §3/§4/§5 重复；`python/fastapi-demo/README.md` 的「接口一览」与 `api.md` 重复（12 行表格维护两遍）。
8. **缺的是「怎么做」而不是「是什么」**：全仓没有任何一处讲「新增一个资源（表 → 模型 → 迁移 → schema → service → api → 测试）该怎么走」，这份内容曾存在于已删除的 `module-map.md`（`git log --all` 无记录，确认为丢失）。
9. **图片资产有两套同名文件**：`docs/design/images/01..05-*.png`（设计稿导出）与 `docs/images/01..05-*.png`（实机截图）名字相同、内容不同，且 04/05 顺序相反（`docs/TECHNICAL_DEBT.md:167` 已记录 T-20，至今未处理）。
10. **链接健康**：全仓相对 Markdown 链接 **0 失效**（本次用脚本对 39 个文档逐条解析），说明上一轮重构的链接治理是有效的；问题集中在「内容陈旧」与「职责重叠」。

一句话结论：**结构已经对了，内容是旧的。** 阶段二应做「瘦身 + 纠错 + 补一条缺失路径」，而不是再换一次目录。

---

## 1. 审查方法与证据来源

| 手段 | 具体做法 | 用途 |
|---|---|---|
| 文件盘点 | `git ls-files` + `wc -l`（54 个 md / 7037 行） | 建立清单与规模基线 |
| 全量阅读 | 逐个读完 39 个非上游文档（含 199 行 PRD、278 行 API 契约、191 行技术债） | 判断职责与准确性 |
| 代码对照 | `.venv/bin/python` 导出 `app.openapi()`（9 path / 14 operation）；`grep` 异常处理器（5 个）、pre-commit（8 钩子）、compose（4 服务）、`Makefile`（13 个 target）、`package.json`（11 个 script） | 校验文档中的数量、命令、路径 |
| 规模对照 | `app/` 1127 行、`tests/` 606 行、`migrations/` 151 行、前端 `src/` 2917 行、`scripts/acceptance.mjs` 388 行 | 判断文档与代码的比例是否失衡 |
| 重复度统计 | 对 12 个高频事实做 `grep -rl` 计数 | 量化重复维护 |
| 链接检查 | Python 脚本解析全部 `[..](..)` 相对链接并验证存在性 | 结果：0 失效 |
| 孤儿检测 | 反向索引：没有任何文档提到文件名/路径的 md | 发现 `docs/prompts/*` 7 个孤儿 |
| 历史核对 | `git log --all -- python/fastapi-demo/docs/module-map.md` | 确认该文件从未入库（信息已丢失，非迁移遗漏） |

**注**：`docs/archive/` 下 3 份调研报告（480 行）按「归档不再更新」的约定，只核对结论去向，不逐条纠错。

---

## 2. 仓库文档总体情况

### 2.1 文档分布

| 类别 | 文件数 | 行数 | 说明 |
|---|---|---|---|
| 根目录 | 3 | 365 | `README.md` 89 / `CONTRIBUTING.md` 57 / `AGENTS.md` 219 |
| `docs/` 人读 | 9 | 1189 | 导航、架构、工具链、状态、债务、需求、设计、验收、部署 |
| `docs/` AI 向 | 19 | 1451 | ADR 6 + 角色卡 6 + 阶段提示词 7 |
| `docs/archive/` | 4 | 480 | 归档报告（不再更新） |
| 后端目录 | 3 | 464 | `README.md` 177 / `docs/api.md` 278 / `app/README.md` 9 |
| 前端目录 | 1 | 140 | `fullstack/product-admin/README.md` |
| **小计（本项目文档）** | **39** | **4089** | — |
| `.agents/skills/`（上游正文） | 15 | 2948 | FastAPI / Vue 官方 Skill，按引用不纳入治理 |
| 合计 | 54 | 7037 | — |

### 2.2 文档 / 代码比例

| 对象 | 代码行 | 对应文档行 | 判断 |
|---|---|---|---|
| 后端 `app/` + `tests/` + `migrations/` | 1884 | 464（README + api.md） | 合理 |
| 前端 `src/` + `scripts/` | 3305 | 140 + design 162 + prd 199 | 偏多，PRD 与设计里各有一份页面清单 |
| 全项目 | 5189 | 4089 | 接近 1:1，对一个学习型项目偏高，但可接受；关键是**去重后能降到约 2800 行** |

---

## 3. 现有文档清单与用途

| # | 文件 | 行 | 现在承担的职责 | 读者 | 准确性 | 处理倾向 |
|---|---|---|---|---|---|---|
| 1 | `README.md` | 89 | 项目定位、两条启动路径、目录、文档入口、常用命令 | 所有人 | ⚠️ 数字过期 | 更新 |
| 2 | `CONTRIBUTING.md` | 57 | 新建项目约定、依赖、提交、**文档约定** | 贡献者 | ⚠️ 与 docs/README 重复 + 1 处过期 | 精简 |
| 3 | `AGENTS.md` | 219 | AI 全局规则、开发原则、质量要求、工作行为 | AI | ⚠️ 定位与现状脱节、缺文档路由 | 补 §0 与路由表 |
| 4 | `docs/README.md` | 80 | 三条阅读路径、文档地图、三层结构、单一事实来源、维护规则 | 所有人 | ⚠️ 2 处事实错 | 更新 |
| 5 | `docs/how-it-works.md` | 137 | 架构图、请求时序、分层职责、数据模型、代码地图、读码顺序 | 开发 | ✅ | 保留 |
| 6 | `docs/toolchain.md` | 121 | 工具链四张图、前后端工具表、CI、命令速查 | 开发 | ✅ | 保留（补测试章节） |
| 7 | `docs/PROJECT_STATUS.md` | 81 | 阶段、已完成、下一步、决策、已知问题、阻塞、仓库状态 | 所有人 | ⚠️ 内部自相矛盾 | 更新 |
| 8 | `docs/TECHNICAL_DEBT.md` | 191 | T-01…T-25 债务登记册 | 开发 / AI | ❌ 大范围过期 | 重写状态位 |
| 9 | `docs/product/prd.md` | 199 | 目标、角色、页面、F-01…F-21、字段、交互、AC-01…AC-15、非目标、Q 表 | 产品 / 开发 | ⚠️ 2 处与实现不符 | 小修 |
| 10 | `docs/design/design.md` | 162 | Token、组件规格、页面规格、稿索引 | 前端 / 设计 | ⚠️ 图片路径与截图描述过期 | 小修 |
| 11 | `docs/delivery.md` | 119 | 验收结论、复跑方式、18 项用例、接口抽查、D/L 记录 | 所有人 | ⚠️ 数字过期 | 更新 |
| 12 | `docs/deploy.md` | 99 | 前置条件、启动、端口、健康检查、备份、运维、排障 | 运维 | ⚠️ 缺环境变量总表 | 补一节 |
| 13 | `python/fastapi-demo/README.md` | 177 | 技术栈、目录、快速开始、迁移、命令、**接口一览**、测试、规范 | 后端 | ⚠️ 3 处过期 + 1 处重复 | 更新 |
| 14 | `python/fastapi-demo/docs/api.md` | 278 | 前后端接口契约（唯一来源） | 前后端 | ⚠️ 1 处数量错 | 小修 |
| 15 | `python/fastapi-demo/app/README.md` | 9 | 7 行目录职责速查 | 后端 | ⚠️ 与 README 目录结构 + how-it-works 分层表三重重叠 | 建议删除 |
| 16 | `fullstack/product-admin/README.md` | 140 | 技术栈、启动、门禁、联调、**页面说明**、校验、目录、设计、限制 | 前端 | ⚠️ 3 处与实现不符 | 更新 |
| 17 | `docs/adr/README.md` + 5 篇 | 297 | 5 条架构决策（Electron / 前端门禁 / Alembic / Docker / 测试基线） | 所有人 | ✅ | 保留 |
| 18 | `docs/agents/README.md` + 5 卡 | 475 | 子智能体角色卡与协作协议 | AI | ⚠️ 2 处触发条件过期 | 更新 |
| 19 | `docs/prompts/*.md` | 679 | 阶段 1–7 的操作提示词 | AI | ✅ 内容可用，但**无入口** | 纳入索引 |
| 20 | `docs/archive/*` | 480 | 三项一次性调研（环境、复用、全景） | 考古 | — | 保留 |

---

## 4. 主要问题分类

### 4.1 A 类：事实陈旧（与当前代码/仓库状态不符）

| 编号 | 位置 | 文档说的 | 实际是 | 证据 |
|---|---|---|---|---|
| A-01 | `README.md:9` | 后端 50 个单测 + 覆盖率 85.12% | 55 个用例 + 85.38% | `make check` 实跑；`docs/PROJECT_STATUS.md:80` 也写 55/85.38 |
| A-02 | `docs/delivery.md:16` | 50 passed + 85.12% | 55 passed + 85.38% | 同上 |
| A-03 | `docs/PROJECT_STATUS.md:22` | 后端 50 例（85.12%） | 55 例（85.38%） | 同文件 §7 第 80 行自相矛盾 |
| A-04 | `python/fastapi-demo/README.md:138` | `make test` 50 个用例 | 55 个 | `uv run pytest` 实测 |
| A-05 | `python/fastapi-demo/README.md:172` | 「没有 Docker / 部署脚本」 | 已有 `Dockerfile`×2、`docker-compose.yml`、`deploy/Caddyfile`、`docs/deploy.md`、ADR-0004 | 仓库根 + `git log` |
| A-06 | `python/fastapi-demo/docs/api.md:8` | 12 个业务操作 | **11 个**业务操作（+3 运维 = 14 operation） | `app.openapi()`：products 6 + categories 5 |
| A-07 | `docs/README.md:40`、`docs/PROJECT_STATUS.md:12` | 12 个业务接口 | 同上，11 | 同上 |
| A-08 | `docs/README.md:69`、`CONTRIBUTING.md:51` | 验收标准在 `prd.md` **第 8 节** | 验收标准是第 **7** 节（第 8 节是「非目标」） | `docs/product/prd.md:136` |
| A-09 | `docs/TECHNICAL_DEBT.md:39-42`（T-01） | `AGENTS.md`、`docs/prompts/` 未入库 | 已随 `c83c4fb` 入库 | `git ls-files AGENTS.md docs/prompts` |
| A-10 | `docs/TECHNICAL_DEBT.md:52`（T-03） | 前端零单测、CI 不覆盖 | Vitest 17 例 + CI `单元测试` 步骤 | `package.json`、`ci.yml` |
| A-11 | `docs/TECHNICAL_DEBT.md:151`（T-12） | `pyproject.toml` 未声明 `requires-python` | 已声明 `>=3.11` | `pyproject.toml:10` |
| A-12 | `docs/TECHNICAL_DEBT.md:155`（T-13） | gh 凭据未接到 git | `~/.gitconfig` 已有 `credential.https://github.com.helper` | `git config --get-regexp credential` |
| A-13 | `docs/TECHNICAL_DEBT.md:184` | 「没有 ADR」（潜在风险表） | 已有 5 篇 ADR + 索引 | `docs/adr/` |
| A-14 | `docs/design/design.md:151-155` | 稿图在 `images/01..05-*.png`（相对 `docs/design/`） | 该目录确实存在同名文件，但与 `docs/images/` 的另一套**同名不同源**；04/05 内容正好互换 | `ls docs/design/images docs/images` |
| A-15 | `docs/design/design.md:151,153` | 「01 商品列表（8 条数据）」「03 分类管理（4 分类）」 | 当前 seed 为 12 商品 / 3 分类；实机 14 商品 | `app/seed.py`、`docs/delivery.md:41` |
| A-16 | `fullstack/product-admin/README.md:93` | 价格「由后端按 `decimal(10,2)` 落库」 | 模型是 `Numeric(8,2)` → `decimal(8,2)` | `app/models/product.py` |
| A-17 | `fullstack/product-admin/README.md:74-78` | 后端启动命令 `uvicorn app.main:app --reload` | 项目已全面 uv 化：`make run` / `uv run uvicorn ...`；裸 `uvicorn` 不在 PATH | `Makefile`、`uv.lock` |
| A-18 | `fullstack/product-admin/README.md:133` | 窄屏（≤960px）统计条自动变 2 列 | 设计规范只承诺 ≥1280px，不承诺移动端 | `docs/design/design.md:139` |
| A-19 | `docs/agents/python-backend-dev.md:81` | `pytest 23 passed` | 55 passed | `make check` |
| A-20 | `docs/agents/README.md:26-27` | 不建 QA 因「前端无 Vitest 套件」；不建 DevOps 因「容器化见 T-09 未开始」 | 两者均已具备 | `package.json`、`docker-compose.yml` |
| A-21 | `CONTRIBUTING.md:26` | 「前端项目提交对应锁文件，例如 `package-lock.json`」 | 本仓库用 `pnpm-lock.yaml` | `fullstack/product-admin/pnpm-lock.yaml` |
| A-22 | `docs/product/prd.md:142-143` | AC-01/02 写死「seed 后 12 条商品」 | 幂等 seed + 历史数据后实测 14 条；PRD §2 自己已写「以 total 实际值为准」 | `docs/delivery.md:41` |

> A-22 属于「可接受的近似」还是「必须改」需要拍板：AC 写死数字会让验收在别人的库上失败。

### 4.2 B 类：职责重叠与重复维护

| 编号 | 重复的事实 | 出现位置（文件数） | 建议权威源 |
|---|---|---|---|
| B-01 | 「文档三层 + 事实单一来源 + 新增文档规则」 | `docs/README.md` §3/§4/§5、`CONTRIBUTING.md` §文档约定（2 处，且措辞略有差异） | `docs/README.md`；CONTRIBUTING 只留一段链接 |
| B-02 | `make check` 是什么 | 10 个文件 | `toolchain.md` 速查表 + `Makefile` |
| B-03 | 后端启动命令 | 根 README、后端 README、toolchain、deploy、`docs/agents/python-backend-dev.md`、`fullstack/.../README.md`（6 处） | 根 README「快速开始」+ 后端 README |
| B-04 | 接口清单（路径 + 说明） | `api.md`（详版）、后端 README「接口一览」12 行、PRD §5 A-01…A-11（3 处） | `api.md` |
| B-05 | 页面/功能清单 | PRD §3 页面表 + §4 功能表、`design.md` §5 页面规格、前端 README「页面说明」（3 处） | PRD（需求）+ design（规格），前端 README 只留路由表 |
| B-06 | 错误码与文案 | `api.md` §1.3、PRD §5 状态码表（2 处） | `api.md`（PRD 引用） |
| B-07 | 「18 项验收」 | 9 个文件 | `delivery.md` |
| B-08 | 端口与地址（8000/5173/4173/8080） | 8 个文件 | `deploy.md` §3 端口表 + 各 README 只写自己那一个 |
| B-09 | 「单测只测 src/api」的边界说明 | 前端 README、ADR-0005、ADR-0002、`docs/agents/vue-frontend-dev.md` | ADR-0005 |
| B-10 | 目录职责速查 | `app/README.md`（9 行）、后端 README 目录树注释、`how-it-works.md` §3 分层表（3 处） | `how-it-works.md` §3 |
| B-11 | 项目定位 | `README.md` 首段、`AGENTS.md` §1、`docs/archive/PROJECT_OVERVIEW.md`（3 处，且口径不同） | `README.md` |

### 4.3 C 类：覆盖缺失

| 编号 | 缺什么 | 为什么需要 | 现状 |
|---|---|---|---|
| C-01 | **「新增一个资源」的端到端步骤** | 这是最高频的开发动作，没有它每个新人都要问一遍 | 原 `python/fastapi-demo/docs/module-map.md` 有「新增资源 7 步」，该文件从未入库，内容已丢失 |
| C-02 | **环境变量总表**（后端 `DATABASE_URL` + compose 的 `MYSQL_*` / `FRONTEND_PORT` / `SITE_ADDRESS`） | 部署最常踩坑的地方，现在分散在 2 个 `.env.example` 与 `deploy.md` 的三处正文里 | 无单一表格 |
| C-03 | **AI 文档路由**（什么任务读哪些文件） | AGENTS.md 只说「读 PROJECT_STATUS」，AI 每次仍要全量翻 docs | 缺失 |
| C-04 | **测试全景一页**（接口层/服务层/前端单测/18 项 E2E 各覆盖什么、不覆盖什么） | 现在拆在 ADR-0005、后端 README、前端 README、toolchain 四处 | 无汇总 |
| C-05 | **阶段路线图与阶段门槛** | PROJECT_STATUS §3 只有 4 条方向，没有「阶段 2 完成的定义」 | 部分 |
| C-06 | **文档地图未收录** `TECHNICAL_DEBT.md`、`docs/prompts/`、`docs/design/mockups/`、`docs/images/` | 导致孤儿与「找不到」 | 缺失 |

### 4.4 D 类：导航与孤儿

- **孤儿**：`docs/prompts/` 7 个文件（679 行）无任何引用，也不在文档地图里。它们是有用的（阶段 1–7 提示词），只是没有入口。
- **导航绕路**：`api.md` 是全仓最高频读取的契约，却在 `python/fastapi-demo/docs/`，从 `docs/README.md` 要用 `../python/fastapi-demo/docs/api.md` 三段相对路径。
- **地图缺行**：`docs/README.md` §2 的 12 行地图里没有 `TECHNICAL_DEBT.md`，而 §5 又要求「新文档必须登记，否则视为孤儿」——自己的规则自己没遵守。
- **图片无索引**：`docs/images/diagram-*.png` 只在 how-it-works/toolchain 的行内引用里出现，没有一处列出「有哪些图、从哪个 md 生成」（生成脚本也没入库）。

### 4.5 E 类：结构与层级

- 目录最深 3 层（`docs/design/images/`、`docs/product/prd.md`），整体健康，无过度拆分。
- 唯一的层级反常：**同类资产两套**（`docs/design/images/` vs `docs/images/`），且 04/05 命名互换，属 T-20 未处理。
- `docs/` 下同时存在「人读 9 个平铺文件」与「AI 向 3 个子目录」，靠 `docs/README.md` 第 3 节说明区分——**是可用的，但依赖读者先读到那一段**。

### 4.6 F 类：AI 协作路由薄弱

| 表现 | 证据 | 影响 |
|---|---|---|
| AGENTS.md 不告诉 AI「读哪份文档」 | 全文只有 `docs/README.md`（第 3 行）与 `docs/PROJECT_STATUS.md`（第 183 行）两处文档指针 | 每次任务要么全读（贵），要么漏读（错） |
| AGENTS.md 与现状脱节 | §1 定位为「AI Agent 应用开发项目」，未提及当前交付是商品管理后台 | 新 AI 会话容易按「Agent 项目」预设立场写代码 |
| 角色卡数字过期 | `python-backend-dev.md:81` 写 23 passed | 验证命令的期望值错误，会让 AI 误判失败 |
| 触发条件过期 | `agents/README.md:26-27` 说「有了 Vitest 再建 QA」「容器化未开始」 | 角色分工与事实不符 |

---

## 5. 重复内容矩阵（量化）

| 事实 | 出现文件数 | 典型文件 |
|---|---|---|
| `make check` | 10 | README、toolchain、delivery、后端 README、agents 卡片 |
| `18 项` 验收 | 9 | delivery、PROJECT_STATUS、ADR-0002、ADR-0005、agents、前端 README |
| `127.0.0.1:8000` | 8 | 根 README、后端 README、前端 README、api.md、deploy、toolchain |
| `pnpm install` | 6 | 根 README、前端 README、toolchain、deploy、agents |
| `pnpm dev` | 6 | 同上 |
| `uv sync` | 5 | 根 README、后端 README、toolchain、agents |
| `docker compose up` | 5 | 根 README、deploy、toolchain、ADR-0004 |
| `/api/products` 路径 | 7 | api.md、PRD、前端 README、后端 README、delivery、agents |
| `8080` | 4 | 根 README、deploy、toolchain、PROJECT_STATUS |
| `product_count` | 3 | api.md、PRD、前端 README |

> 结论：**命令与端口属于「必须重复但要短」**（速查表 + 局部提及），**接口清单、错误码、页面清单属于「必须唯一」**。前者靠表格收敛长度，后者靠删除副本。

---

## 6. 文档与代码冲突清单（需人工确认的项）

| 编号 | 冲突 | 证据 | 处理建议 |
|---|---|---|---|
| X-01 | PRD AC-08 要求「编辑只提交 `stock` 字段（PATCH）」，前端实际提交整表单 | `fullstack/product-admin/src/components/ProductFormDialog.vue`；`docs/delivery.md` 未记录该偏差 | 记为已知偏差（不阻塞），或在 PRD 注明「实现为整表单提交，语义等价」 |
| X-02 | PRD AC-01/02 写死 12 条商品，实测库 14 条 | `docs/delivery.md:41` | PRD 改为「以 `/api/products/count` 实际值 N 为准」 |
| X-03 | 后端 README 说「没有 Docker」，仓库已有完整容器化 | 根目录 `docker-compose.yml`、`python/fastapi-demo/Dockerfile` | 直接改 |
| X-04 | `api.md:8` 与 PRD「11 个接口」矛盾 | `app.openapi()` = 11 业务 + 3 运维 | 统一为 11 / 14 |
| X-05 | 设计稿描述「8 条商品 / 4 分类」，与当前 seed（12 / 3）不符 | `docs/design/design.md:151,153` | 描述改为「设计稿为示意数据」 |
| X-06 | 前端 README「`decimal(10,2)`」 | 模型 `Numeric(8,2)` | 直接改 |
| X-07 | AGENTS.md 项目定位 vs README 定位 | `AGENTS.md:5-21` vs `README.md:1-4` | 在 AGENTS §0 加「当前阶段与交付物」一段并链接 README，保留长期目标 |
| X-08 | 两套同名图片 | `docs/design/images/`、`docs/images/` | 改名（见计划 §4） |

**待确认（无足够证据判断）**：
- `docs/archive/REUSE_CANDIDATES.md` 里对「Tauri 未采用 / Electron 采用」的表述是否与新 ADR-0001 完全一致（归档不再更新，仅需在归档 README 标注「结论已迁至 ADR-0001」）。
- `docs/deploy.md` 的 Caddy 段描述 HTTPS 自动签发，本轮容器验证**未启用 `https` profile 实测**（当时只验证了 HTTP 路径）——文中已注明「可选」，但未说明「未实测」。

---

## 7. 缺失的重要信息（按影响排序）

1. **新增资源的实现路径**（C-01）——影响每个新增功能。
2. **AI 路由表**（C-03）——影响每次 AI 会话的成本与准确率。
3. **环境变量总表**（C-02）——影响首次部署成功率。
4. **测试全景**（C-04）——影响「改了要不要补测试」的判断。
5. **文档地图补漏**（C-06）——`TECHNICAL_DEBT.md`、`prompts/`、`mockups/`、`images/` 未登记。
6. **图片生成方式**（`docs/images/diagram-*.png` 由何种脚本产出）——目前脚本在 `/tmp`，未入库，图与 mermaid 源可能失同步。

---

## 8. 逐文件处理建议

| 文件 | 处理 | 理由 |
|---|---|---|
| `README.md` | **更新**（数字 2 处、命令保持） | 入口文档，错误数字最先被看到 |
| `AGENTS.md` | **增补**（§0 现状定位 + §9 文档路由表），不删现有原则 | 219 行原则仍有价值，问题是没有路由 |
| `CONTRIBUTING.md` | **精简**（文档约定降为一段 + 链接；修 `package-lock.json`） | 与 docs/README 重复，属 B-01 |
| `docs/README.md` | **更新**（修 2 处事实、补 4 行地图、增「新增功能从哪开始」入口） | 唯一导航，必须准 |
| `docs/how-it-works.md` | **保留**，补一节「新增一个资源要改哪些文件」（消化 C-01） | 架构文档天然承载「改哪里」 |
| `docs/toolchain.md` | **保留**，补「测试金字塔」小节（消化 C-04） | 工具链文档天然承载测试工具 |
| `docs/PROJECT_STATUS.md` | **更新**（数字、接口计数、决策表引用 ADR） | 唯一进度源，必须自洽 |
| `docs/TECHNICAL_DEBT.md` | **重写状态位**（T-01/03/12/13/19 关闭、T-04 进度更新、删除「无 ADR」行、更新基线与日期） | 当前最大面积过期源（A-09…A-13） |
| `docs/product/prd.md` | **小修**（AC 条数改为 N、A-01…A-11 加「路径以 api.md 为准」、Q-02 结论） | 需求本身稳定，只有数字与引用需校准 |
| `docs/design/design.md` | **小修**（图片路径与命名、稿内数据说明） | A-14/A-15 |
| `docs/delivery.md` | **更新**（55/85.38、图片引用、补 X-01 偏差记录） | A-02 |
| `docs/deploy.md` | **补一节**「环境变量总表」+ 标注 Caddy/HTTPS 未实测 | C-02、X 待确认项 |
| `python/fastapi-demo/README.md` | **更新**（55、删除「没有 Docker」、接口一览改为链接、相关文档补全） | A-04/A-05/B-04 |
| `python/fastapi-demo/docs/api.md` | **小修**（12→11） | A-06 |
| `python/fastapi-demo/app/README.md` | **删除**，7 行职责并回 `how-it-works.md` §3 | 三重重叠（B-10），价值最低 |
| `fullstack/product-admin/README.md` | **更新**（decimal、启动命令、响应式表述、页面表降级为路由表） | A-16/A-17/A-18/B-05 |
| `docs/adr/*` | **保留** | 决策记录准确 |
| `docs/agents/README.md` + 卡片 | **更新**（23→55、QA/DevOps 触发条件、T-09 引用） | A-19/A-20 |
| `docs/prompts/*` | **保留并登记**进文档地图（不重写内容） | 有用的阶段提示词，只是缺入口 |
| `docs/archive/*` | **保留**，仅在 `archive/README.md` 补「结论已迁至 ADR-xxxx」索引 | 归档规则 |
| `docs/design/mockups/*.html` | **保留**（设计源文件），在地图里登记 | 当前无入口 |
| `docs/images/diagram-*.png` | **保留**，在 how-it-works/toolchain 各加「由 mermaid 渲染，源见本文件 XX 节」说明 | 防失同步 |

---

## 9. 不纳入治理范围

| 对象 | 理由 |
|---|---|
| `.agents/skills/**`（15 文件 / 2948 行） | 上游官方正文，只在 `SOURCE.md` 记录来源与本地适配；不按本项目风格改写 |
| `node_modules/`、`.venv/`、`dist/`、`.acceptance/`、`pnpm-store/` | 产物与缓存，已被 gitignore |
| `app/README.md` 之外的 `.py` 注释 | 属代码注释，不属文档体系 |
| `docs/archive/*` 正文 | 归档不再更新 |

---

## 10. 交给阶段二的问题

1. `api.md` 是否迁到 `docs/api.md`（收益：导航短、与「前后端契约」定位一致；成本：5–7 处引用重写）？
2. `app/README.md`（9 行）是否删除并把内容并入 `how-it-works.md`？
3. PRD 的 AC 数字（12 条）改为「以实际 total 为准」是否可接受？
4. 两套同名图片如何命名（`design-*` / `shot-*`）？
5. `docs/prompts/` 是否保留在 `docs/` 顶层，还是移入 `docs/agents/prompts/`（AI 向聚合）？
6. 是否允许在 CI 增加一个「文档链接检查」步骤（零依赖、Node 内置 fs，约 40 行）？
