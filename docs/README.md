# 文档导航 · 先读这一页

项目：**商品管理后台**（Vue 3 + FastAPI + MySQL），一个可以本地跑、也可以容器部署的全栈应用。
你现在在 `docs/` 目录，这里是全部文档的入口。

## 1. 三条阅读路径（按你的时间选）

### A. 只有 10 分钟：知道这东西是干嘛的

1. 本文第 2 节「文档地图」扫一遍表格
2. [`../README.md`](../README.md) 的「这个项目是什么」与「快速开始」
3. `docs/how-it-works.md` 的第 1 节架构图

### B. 有 40 分钟：能看懂代码、能改点东西

1. [`how-it-works.md`](how-it-works.md) —— 请求怎么走、为什么分四层、数据长什么样（含 3 张图）
2. [`toolchain.md`](toolchain.md) —— 每个工具解决什么问题、三条命令链路（含 2 张图）
3. [`../README.md`](../README.md) 的「快速开始」，真的跑一遍
4. `how-it-works.md` 第 6 节的「读代码顺序」，跟着走一遍

### C. 要动手改功能：知道规矩在哪

在上述基础上，按需查阅：

- 要改接口 → [`../docs/api.md`](api.md)（唯一契约）
- 要改需求 → [`product/prd.md`](product/prd.md)
- 要改样式 → [`design/design.md`](design/design.md)
- 要改部署 → [`deploy.md`](deploy.md)
- 想知道「当初为什么这么选」→ [`adr/`](adr/README.md)
- 想知道「现在到哪一步」→ [`PROJECT_STATUS.md`](PROJECT_STATUS.md)

## 2. 文档地图

| 文档 | 给谁 | 一句话 | 什么时候读 |
|---|---|---|---|
| [`../README.md`](../README.md) | 所有人 | 项目简介 + 两条启动路径 | 第一次来 |
| [`how-it-works.md`](how-it-works.md) | 开发 | **系统怎么跑起来**：架构、请求时序、数据模型 | 想看懂代码 |
| [`toolchain.md`](toolchain.md) | 开发 | **工具怎么用**：uv / pnpm / ruff / Alembic / CI 各自解决什么 | 跑不起来、不知道敲什么命令 |
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | 所有人 | 现在完成到哪、下一步做什么、有哪些已知问题 | 每次开工前 |
| [`api.md`](api.md) | 前后端 | 接口契约：11 个业务接口 + 3 个运维路径（参数/响应/错误文案） | 调接口、改接口 |
| [`product/prd.md`](product/prd.md) | 产品 / 开发 | 需求与验收标准（P0 十六条 + AC 十五条） | 确认「要做什么」 |
| [`design/design.md`](design/design.md) | 前端 / 设计 | 视觉规范与组件规格（token、行高、状态色） | 动界面之前 |
| [`delivery.md`](delivery.md) | 所有人 | 交付清单：验收结果、已知限制 | 想知道「做到了没有」 |
| [`deploy.md`](deploy.md) | 运维 / 部署 | 容器化部署、健康检查、备份、排障 | 要上服务器 |
| [`adr/`](adr/README.md) | 所有人 | 5 条架构决策记录：为什么用 Electron / Alembic / Docker / 轻量前端门禁 | 想质疑或推翻某个选择 |
| [`agents/README.md`](agents/README.md) | AI 协作者 | 子智能体角色卡与协作协议 | 派活给 AI 时 |
| [`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md) | 开发 / 决策 | 技术债清单：每条带证据、优先级、成本、是否已解决 | 排期、评估「该不该现在修」 |
| [`playbooks/`](playbooks/README.md) | AI 协作者 | 7 份阶段任务手册（认识项目 → AI 基建 → 架构 → 部署 → 计划 → 单任务 → 审查） | 开新一轮系统性工作时 |
| [`design/mockups/`](design/mockups/) | 前端 / 设计 | 5 张可交互 HTML 设计稿（1440×900，无 CDN 依赖） | 对像素、确认交互细节 |
| [`images/`](images/) | 所有人 | 实机截图 5 张（`shot-*`）+ 5 张图（`diagram-*`，由 how-it-works / toolchain 的 mermaid 导出；**权威版本是 md 里的代码块**） | 写文档、贴 PR |

## 3. 文档分三层，不要混着读

```
人读的（约 1348 行）      你现在该看的：README、how-it-works、toolchain、PROJECT_STATUS、
                          prd、design、delivery、deploy、api
AI 读的（约 1739 行）      AGENTS.md、agents/、adr/、playbooks/ —— 给 AI 的作业指导书
归档的（约 672 行）        archive/ 与技术债清单 —— 结论已经写进 ADR 与 STATUS
```

**如果你只想知道「这项目现在怎么样」，读 `PROJECT_STATUS.md` 一页就够。**

## 4. 事实只有一个来源

同一条信息只允许写在一处，其他地方用链接指过来。改的时候改源头：

| 事实 | 唯一来源 | 别处只能 |
|---|---|---|
| 接口路径 / 参数 / 错误文案 | `docs/api.md` | 引用 |
| 后端命令（make xxx） | `python/fastapi-demo/Makefile` + [`toolchain.md`](toolchain.md) §6 速查表 | 引用 |
| 前端命令（pnpm xxx） | `fullstack/product-admin/package.json` + [`toolchain.md`](toolchain.md) | 引用 |
| 验收标准 | [`product/prd.md`](product/prd.md) 第 7 节 | 引用 |
| 验收结果 | [`delivery.md`](delivery.md) | 引用 |
| 视觉规范 | [`design/design.md`](design/design.md) | 引用 |
| 技术选型理由 | [`adr/`](adr/README.md) | 引用 |
| 当前进度 / 单测数量与覆盖率 | [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | 引用 |
| 端口 / 环境变量 | [`deploy.md`](deploy.md) §3–§3.1 | 只写自己那一个端口 |

## 5. 维护规则

1. **改了代码就改对应文档**，并在同一次提交里完成——文档落后于代码比没有文档更糟。
2. **不要新增「总结性」文档**。想补充信息，先找上表里有没有该更新的一行。
3. 新文档必须在本页地图里登记，否则视为孤儿文件。
4. AI 向文档（`AGENTS.md`、`agents/`、`adr/`、`prompts/`）在文件开头有统一标注，人读文档不带该标注——**看到标注就可以先跳过**。
