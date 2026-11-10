# ADR-0010：Agent 执行循环用自研最小实现，不引编排框架

- 状态：**提议（待用户确认）**
- 日期：2026-11-10
- 相关：阶段 5、[`docs/agent.md`](../agent.md)

## 背景

阶段 5 要把「一问一答」升级成「模型自己决定用不用工具、用几次、何时收尾」的执行循环。
现状：`backend/app/llm/` 已有 `LLMClient` 协议（`chat` / `stream`），对话接口是单次补全，
没有任何工具调用、步数控制或运行记录。

主流方案有四种（详见 [`docs/agent.md`](../agent.md) §2）：单 agent 工具循环（Anthropic / Claude Agent SDK）、
图状状态机（LangGraph）、SDK Runner（OpenAI Agents SDK）、多 agent 编排（CrewAI / AutoGen）。

## 决策

**自研一个约 250 行的执行器，实现「单 agent 工具循环」，不引入 LangGraph / OpenAI Agents SDK / CrewAI。**

具体六条：

1. **循环原语照抄主流做法**：请求 → 模型返回 `tool_calls` 或最终文本 → 执行工具 → 结果回灌 → 再请求；
   没有 `tool_calls` 即收尾。这是四类架构的共同内核。
2. **状态显式落库**：`agent_runs` + `agent_steps` 两张表，每步一条记录。
   不为「以后做图」提前建通用状态机，但把状态存成可回放的有序步骤——这是 LangGraph 的 checkpointer、
   Agents SDK 的 `new_items` 给我们的同类能力，只是用两张表实现。
3. **预算与护栏在循环里硬编码**：最大 8 步、单工具 2s、连续 3 次同类失败中止、模型超时沿用 `LLM_TIMEOUT_SECONDS`。
   不提供配置文件开关（先固定，等有真实场景需要再外置）。
4. **工具白名单 + 参数校验 + 只读**：v1 三个内置工具（`calculator` / `now` / `search_conversations`），全部只读，
   全部强制带 `user_id`。没有写操作就不需要审批环节。
5. **事件协议复用对话的 SSE 做法**：`POST` + `text/event-stream`，开流前错误仍是普通 JSON，
   开流后一律 200、错误走 `error` 事件。
6. **前端把「执行过程」与「对话内容」分开**：时间线来自 `agent_steps`，对话消息只在 `run_finished` 时落一条。

## 代价

- **要自己维护循环正确性**：终止条件、重试、回滚、并发控制都得自己写对。框架能省掉这部分。
- **没有现成的可视化与回放工具**：LangGraph 有 Studio，Agents SDK 有 tracing；我们只有 `agent_steps` 表和前端时间线。
- **后续接多 agent 时要改结构**：现在的循环是单 agent 的，加 handoff 需要重构执行器（估计 150 行左右的改动）。
- **工具生态要自己接**：MCP 在阶段 7 才做，那时需要把工具层从「进程内注册表」扩到「外部协议」。

## 被否方案

| 方案 | 否决理由 |
|---|---|
| LangGraph | 引入整套状态图概念 + 依赖（含 `langchain-core`）；当前只有一个 agent、线性循环，用不上图能力，却要付学习与升级成本 |
| OpenAI Agents SDK | 绑定 OpenAI 的抽象（handoff/guardrails/tracing），我们的模型层已自建 `LLMClient`，再接一套会形成两套抽象并存；且它假定能直连 OpenAI 风格端点（我们还要支持 fake 与自定义 base_url） |
| CrewAI / AutoGen | 面向多 agent 协作，本阶段只有一个 agent；引入后要按它们的角色/任务模型重写业务 |
| 直接暴露框架的「图」给前端 | 前端只需要「第几步、调了什么、结果如何」，图结构对 UI 没有价值，反而增加协议复杂度 |
| 不做步数落库、只在内存里跑 | 刷新即丢、失败无法排查；SSE 断流后用户看不到刚才发生了什么 |

## 复评触发

出现以下任一情况，重新评估是否引入框架：

1. 需要 **多 agent 协作**（handoff / supervisor 模式）。
2. 需要**断点续跑**或**跨进程恢复**（例如把执行放到独立 worker）。
3. 工具数量超过 **15 个**，或需要按用户/角色做**工具权限分级**与**人工审批**。
4. 循环逻辑出现**第三次同类缺陷**（终止、重试、并发），说明自研维护成本已经高于引入框架。

## 落地记录

待实现后补（T1–T7 完成后回填：实际代码量、发现的坑、与设计的偏差）。
