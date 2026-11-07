# ADR-0006 对话落库与模型客户端抽象

> **AI 向文档**：架构决策记录，人与 AI 共读；每条决策的「为什么」是重点。总入口见 [`../README.md`](../README.md)。

- 状态：**已采纳**
- 日期：2026-11-07
- 相关：[阶段 4 设计](../chat.md)、[PROJECT_STATUS §3](../PROJECT_STATUS.md)、[playbooks/05 §一](../playbooks/05-development-plan-and-mvp-tasks.md)

## 背景

进入阶段 4「LLM 接入与基础对话」，有两件事必须先定：对话数据存哪、模型怎么接。

如果把对话放在前端内存里，刷新即丢，阶段 5（Agent 执行循环）、阶段 8（RAG / Memory）、阶段 9（多 Agent）都需要「历史对话」作为输入，届时还要推翻重做。模型接入则有两个现实约束：CI 不能依赖外部网络，本地开发也不一定有 API key。

## 决定

1. **对话落库**：新增 `conversations` 与 `messages` 两张表，走 Alembic 迁移（与 categories / products 同一套，ADR-0003）。
   - `conversations`：`title`、`agent_key`（预留多 Agent）、`update_time`（列表按最近活动倒序）。
   - `messages`：`conversation_id`（外键，级联删除）、`role`、`content`、`model`。
   - 上下文策略：发消息时取最近 20 条；摘要压缩留给阶段 8。
2. **模型客户端抽象**：`LLMClient` 协议 + `LLMReply`，实现两个——`FakeLLM`（默认）与 `OpenAICompatibleClient`（httpx）。
   - 通过 `settings.llm_provider` 选择，经 FastAPI `Depends` 注入，测试用 `dependency_overrides` 替换。
   - 默认 `fake`：CI 与无 key 的本地环境都能跑完整链路。
   - 接入真实模型只换实现，服务层与接口层不动。
3. **对话内接口首版同步返回**，SSE 流式作为阶段 4 的第二批任务（T4b）。

## 代价

- 多两张表与至少一个迁移；删会话必须级联删消息（外键 `ondelete` + 关系配置两处都要对）。
- 上下文只取最近 20 条，长对话会「忘事」——这是阶段 8 要解决的问题，不是 bug。
- `OpenAICompatibleClient` 只能覆盖兼容 `/chat/completions` 的服务；真要接非兼容协议（如某些厂商的原生 API）需要再加实现。
- `fake` 默认值有被误带到生产的风险：`deploy.md` 与 `.env.example` 里必须显式写 `LLM_PROVIDER`，且响应里带上 `model` 字段便于一眼识破。

## 被否方案

| 方案 | 否掉的原因 |
|---|---|
| 对话不落库，前端自己存 | 刷新即丢；阶段 5/8/9 都要历史，届时返工 |
| 落库但只存「一个会话」单表 | 多会话是明确需求，改表比建表贵 |
| 引入 LangChain / LlamaIndex 做模型层 | 阶段 4 只需要「发请求拿文本」，框架带来的抽象成本大于收益；等阶段 5 选 Agent 框架时再评估 |
| 直接调 SDK（openai-python）而非 httpx | 多一个重依赖；兼容端点用得上的只有一次 POST，`httpx` 已在间接依赖里 |
| 首版就做流式 | 先把存储与错误处理做对，流式是叠加层，单独一批更安全 |
