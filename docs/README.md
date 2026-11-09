# 文档导航 · 先读这一页

项目：**My Agent**（Vue 3 聊天界面 + FastAPI + MySQL + 可切换的模型层），一个可以本地跑、也可以容器部署的 AI 应用。
你现在在 `docs/` 目录，这里是全部文档的入口。

> 商品管理后台（商品 / 分类 / 概览）已于 2026-11-08 归档，相关代码与需求/设计/验收文档在 [`archive/product-admin/`](../archive/product-admin/README.md)，日常不需要看。

## 1. 三条阅读路径（按你的时间选）

### A. 只有 10 分钟：知道这东西是干嘛的

1. 本文第 2 节「文档地图」扫一遍表格
2. [`../README.md`](../README.md) 的「这个项目是什么」与「快速开始」
3. `docs/how-it-works.md` 的第 1 节架构图

### B. 有 40 分钟：能看懂代码、能改点东西

1. [`how-it-works.md`](how-it-works.md) —— 请求怎么走、为什么这样分层、数据长什么样（含 3 张图）
2. [`toolchain.md`](toolchain.md) —— 每个工具解决什么问题、四条命令链路（含 3 张图）
3. [`../README.md`](../README.md) 的「快速开始」，真的跑一遍
4. `how-it-works.md` 第 6 节的「读代码顺序」，跟着走一遍

### C. 要动手改功能：知道规矩在哪

在上述基础上，按需查阅：

- 要改接口 → [`api.md`](api.md)（唯一契约：对话 7 个操作 + 3 个探针）
- 要改对话逻辑 / 接模型 → [`chat.md`](chat.md)、[ADR-0006](adr/0006-llm-client-and-chat-storage.md)
- 要加登录 / 鉴权 / 数据隔离 → [`auth.md`](auth.md)、[ADR-0008](adr/0008-auth-and-session.md)
- 要改界面 → [`../frontend/README.md`](../frontend/README.md) 与 `frontend/src/views/ChatView.vue`
- 要改部署 → [`deploy.md`](deploy.md)
- 想知道「当初为什么这么选」→ [`adr/`](adr/README.md)
- 想知道「现在到哪一步」→ [`PROJECT_STATUS.md`](PROJECT_STATUS.md)

## 2. 文档地图

| 文档 | 给谁 | 一句话 | 什么时候读 |
|---|---|---|---|
| [`../README.md`](../README.md) | 所有人 | 项目简介 + 两条启动路径 | 第一次来 |
| [`how-it-works.md`](how-it-works.md) | 开发 | **系统怎么跑起来**：架构、请求时序、数据模型、分层理由 | 想看懂代码 |
| [`toolchain.md`](toolchain.md) | 开发 | **工具怎么用**：uv / pnpm / ruff / Alembic / CI 各自解决什么 | 跑不起来、不知道敲什么命令 |
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | 所有人 | 现在完成到哪、下一步做什么、有哪些已知问题 | 每次开工前 |
| [`api.md`](api.md) | 前后端 | 接口契约：对话 7 个操作 + 3 个运维路径（参数/响应/错误文案） | 调接口、改接口 |
| [`chat.md`](chat.md) | 前后端 | **对话功能设计**：表结构、接口、模型抽象、任务拆分与验收 | 要改对话、接模型时 |
| [`auth.md`](auth.md) | 前后端 | **账号体系设计**：个人助手绑哪些数据、会话鉴权选型、隔离规则、任务拆分 | 要加登录、查数据归属时 |
| [`deploy.md`](deploy.md) | 运维 / 部署 | 容器化部署、健康检查、备份、排障 | 要上服务器 |
| [`adr/`](adr/README.md) | 所有人 | 架构决策记录：为什么 Electron / Alembic / Docker / 轻量前端门禁 / 模型抽象 | 想质疑或推翻某个选择 |
| [`agents/`](agents/README.md) | AI 协作者 | 子智能体角色卡与协作协议 | 派活给 AI 时 |
| [`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md) | 开发 / 决策 | 技术债清单：每条带证据、优先级、成本、是否已解决 | 排期、评估「该不该现在修」 |
| [`playbooks/`](playbooks/README.md) | AI 协作者 | 7 份阶段任务手册（认识项目 → AI 基建 → 架构 → 部署 → 计划 → 单任务 → 审查） | 开新一轮系统性工作时 |
| [`images/`](images/) | 所有人 | 5 张图（`diagram-*`，由 how-it-works / toolchain 的 mermaid 导出；**权威版本是 md 里的代码块**） | 写文档、贴 PR |
| [`archive/`](archive/README.md) | 所有人 | 历史调研报告（结论已并入 ADR / STATUS） | 想追溯当初怎么判断的 |
| [`../archive/product-admin/`](../archive/product-admin/README.md) | 所有人 | 已归档的商品管理模块（前后端代码、需求/设计/验收、截图） | 要恢复或参考旧实现时 |

## 3. 文档分三层，不要混着读

```
人读的（约 900 行）       README、how-it-works、toolchain、PROJECT_STATUS、api、chat、deploy
AI 读的（约 1700 行）     AGENTS.md、agents/、adr/、playbooks/ —— 给 AI 的作业指导书
归档的（约 3000 行）      docs/archive/（调研报告）、archive/product-admin/（已下线模块）、TECHNICAL_DEBT
```

- **人读**：解释「为什么」，按上面的阅读路径顺序读。
- **AI 读**：给 AI 的作业指导书，人也可以用，但密度更高。
- **归档**：结论已经迁走，只在追溯时看；不要从归档文档里抄现状。

## 4. 事实只有一个来源

同一件事只在一个地方定义，其他地方只链接、不复述：

| 事实 | 唯一来源 |
|---|---|
| 接口参数、响应、错误文案 | [`api.md`](api.md) |
| 分层、目录职责、请求链路 | [`how-it-works.md`](how-it-works.md) |
| 命令、工具职责、CI 步骤 | [`toolchain.md`](toolchain.md) |
| 端口、环境变量、容器服务 | [`deploy.md`](deploy.md) §3–§3.1 |
| 对话表结构、事件协议、任务拆分 | [`chat.md`](chat.md) |
| 当前进度、单测数量与覆盖率 | [`PROJECT_STATUS.md`](PROJECT_STATUS.md) |
| 技术选择与理由 | [`adr/`](adr/README.md) |
| 已知问题与债 | [`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md) |

## 5. 维护规则

1. 新增文档前先问：能不能并进上面某一份？能就别新建。
2. 新建的文档必须登记到本文第 2 节的表里，否则视为孤儿。
3. 改代码的同一个提交里改对应文档；过期内容直接改写，不叠加「补充说明」。
4. 一份文档只服务一类读者：人读的不要塞 AI 作业指令，AI 向的不要写教学式解释。
