# Python Agent 开发面试问答

以 My Agent 项目为例。面试时可以用同一个场景串起全程：**用户说「找出我最近的会议纪要，再把当前会话改名为『会议跟进』」**。这道题能同时考到上下文、工具调用、读写权限、审批和流式展示。

## 一、Python 数据类型与类型系统

**面试官：开发 Agent 最常用哪些 Python 数据类型？怎么选？**

**候选人：** 我用 `list` 保存按顺序排列的消息，用 `dict` 表示 JSON 请求体和工具参数，用 `set` 做工具白名单和去重，用 `tuple` 表示固定组合。正文和 JSON 文本是 `str`，HTTP 流读到的可能是 `bytes`，解码时要考虑一个中文字符可能跨两个数据块。用 `None` 表示没有值时，我会明确区分它和 `""`、`0`、`False`，这些都可能是业务上的有效值。

**面试官：为什么 `def run(messages=[])` 容易出问题？**

**候选人：** 默认参数在函数定义时创建，后续调用共用同一个列表。一次运行追加的工具结果可能进入下一次运行。我会写成 `messages=None`，在函数内创建新列表。还有一个类似的坑，`history.copy()` 只复制外层列表，里面的消息字典仍可能共享。需要改某条消息时，我会为那条消息建新对象。

**面试官：`TypedDict`、`dataclass`、Pydantic 和 `Protocol` 分别用在哪里？**

**候选人：** `TypedDict` 给内部字典约定字段，项目用它描述 `ToolCall` 和 `ToolCallReply`。`dataclass` 适合表示模型配置和运行状态。FastAPI 请求体和外部工具参数需要运行时校验，可用 Pydantic 模型或 JSON Schema 校验器。`Protocol` 用来约定可替换对象的接口，项目里的 `LLMClient` 让执行器能接真实模型，也能接测试用的 `FakeLLM`。类型注解帮助静态检查，外部输入仍要在运行时校验。 [Python typing 文档](https://docs.python.org/3/library/typing.html) · [项目 LLMClient](../backend/app/llm/base.py#L91)

## 二、HTTP、异常、生成器和异步

**面试官：`return`、`yield` 和 `await` 在 Agent 里各做什么？**

**候选人：** `return` 适合一次返回一个模型结果。`yield` 让生成器逐个产出事件，比如先发「调用工具」，再发「工具结果」。`await` 用于等待异步 I/O，比如用 `httpx.AsyncClient` 等待上游响应，让事件循环在这期间处理其他任务。My Agent 当前的模型客户端使用同步 HTTPX，Agent 事件通过同步生成器产出。升级为异步时，HTTP 客户端和其他阻塞 I/O 也要一起考虑。 [Python asyncio 文档](https://docs.python.org/3/library/asyncio-task.html) · [项目 SSE 编码](../backend/app/api/sse.py#L16)

**面试官：为什么 HTTP 客户端和流式响应常用 `with`？你会怎么处理异常？**

**候选人：** `with` 管理连接和响应的生命周期，异常退出时也能清理资源。服务里可以复用 `Client` 的连接池。错误处理要分清连接或读取超时、HTTP 状态错误、返回 JSON 结构不符合预期、模型给出无效工具参数。每类错误的处理路径不同。比如模型参数填错，可以返回一条工具错误让模型修正。认证失败应提示检查配置。 [HTTPX Clients 文档](https://www.python-httpx.org/advanced/clients/) · [项目模型错误处理](../backend/app/llm/openai_compatible.py#L100)

## 三、Python 怎么调用 LLM API

**面试官：给你 `base_url`、API Key 和模型名，Python 怎么拿到一次回复？**

**候选人：** 对 OpenAI Chat Completions 兼容接口，我用 `httpx.Client.post()`，把有序的 `messages` 和 `model` 放入 JSON，用 Bearer 认证并设置超时。先检查 HTTP 状态，再读取 `choices[0].message.content`。下面是一个纯文本补全示例，`base_url` 应包含服务要求的版本路径，例如 `/v1`。 [OpenAI Chat Completions API](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create)

```python
import httpx


def chat(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    response = client.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages},
        timeout=10.0,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("模型未返回文本")
    return content
```

**面试官：加上流式输出和工具调用，代码会有什么变化？**

**候选人：** 文本流式补全会发送 `stream=True`，持续读取 SSE，提取每帧里的 `delta.content`。工具补全会在请求里带工具名称、描述和参数 Schema，响应可能包含 `tool_calls`。执行器拿到调用后，先做参数和权限检查，再运行工具，把带调用 ID 的结果交回模型。项目把三种能力定义成 `chat()`、`stream()` 和 `chat_with_tools()`，其中 `chat_with_tools()` 一次读取完整的模型响应。 [项目接口定义](../backend/app/llm/base.py#L91) · [项目 HTTPX 实现](../backend/app/llm/openai_compatible.py#L112)

## 四、多个 LLM API 怎么复用一套代码

**面试官：接三家模型供应商，要写三套 Agent 吗？**

**候选人：** 一套 Runtime 就够。使用同一种兼容协议的服务，可以共用一个客户端，通过配置选择 `base_url`、`api_key`、`model` 和超时。协议有差异时，我会按协议增加适配器。Runtime 传统一的消息和工具声明，适配器负责转换请求、解析回复、回传工具结果并归一化错误。My Agent 当前的工厂支持 `FakeLLM` 和 `OpenAICompatibleClient`。下表的 Responses 和 Claude 原生接口是扩展设计示例。 [项目模型工厂](../backend/app/llm/__init__.py#L93)

| API 协议 | 文本输入 | 输出上限字段 | 工具结果怎么回传 |
|---|---|---|---|
| OpenAI Chat Completions | `messages` | `max_completion_tokens` | `role="tool"`，带 `tool_call_id` |
| OpenAI Responses | `input`，可配 `instructions` | `max_output_tokens` | `function_call_output`，带 `call_id` |
| Claude Messages | `messages`，系统提示用顶层 `system` | `max_tokens` | 在用户消息中放 `tool_result`，用 `tool_use_id` 配对 |

[Chat Completions API](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create) · [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) · [Claude Messages API](https://platform.claude.com/docs/en/api/python/messages/create)

**面试官：参数兼容是不是做一张字段名映射表就行？**

**候选人：** 字段映射只解决一部分。我会先定义业务参数，比如 `output_token_limit`，再由适配器按协议构造请求。还要检查具体模型支持的能力，包括工具调用、流式返回、并行工具和结构化输出。用户选了某个能力而模型不支持时，应该在运行前报出具体原因。另外，工具调用 ID、消息块顺序、流式事件和停止原因都有协议差异。适配测试要覆盖完整的一次「模型请求工具 → 回传结果 → 模型作答」，只测纯文本容易漏掉这些问题。

## 五、怎么设计 Tool

**面试官：把一个 Python 函数给模型调用，需要设计哪些东西？**

**候选人：** 我会定义三部分。第一部分是给模型看的工具名、用途和参数 Schema。第二部分是运行时注册表，用 `dict` 按工具名定位已注册的实现。第三部分是执行策略，包括参数校验、权限、超时、预算和审批。例如 `rename_conversation` 只需要模型提供 `title`，登录用户和当前会话由应用侧确定。结果要能区分成功、可纠正的参数错误和执行状态未知，方便下一轮做判断。 [项目工具注册表](../backend/app/agent/tools/__init__.py#L92) · [项目 ToolPolicy](../backend/app/agent/policy.py#L77)

**面试官：模型传的参数已经有 Schema，为什么还要校验？Tool、MCP、Skill 分别是什么？**

**候选人：** Schema 帮助模型生成参数，服务端仍要解析 JSON，检验类型和范围，再检查用户权限及当前状态。模型输出、MCP 返回值和检索到的文字都属于外部数据。Tool 是一次可执行的操作，MCP 是发现和调用外部工具的一种协议，Skill 是给 Agent 的任务指引和参考资料。在这个项目里，Skill 可以缩小工具集合，实际执行权限仍由 Tool Policy 决定。 [项目工具与 Skill 链路](../docs/code-reading-guide.md#L61)

## 六、怎么实现 Agent Runtime

**面试官：从用户点发送，到看到过程和最终回答，中间发生了什么？**

**候选人：** 我把一次 Agent 请求建模为一个 `run`，把工具请求、结果和最终回复记成有序的 `step`。以「找会议纪要并改名」为例，流程是这样的。

1. **发送与建档。** 前端开启「深度回答」后向 `POST /api/conversations/{id}/agent/stream` 发请求。FastAPI 校验身份、会话归属和运行状态。`prepare_run()` 组装历史上下文，并在开流前提交用户消息、`AgentRun` 和首个步骤。
2. **让模型决定下一步。** `_run_loop()` 把对话、已加载的 Skill 指引和可用工具交给 `llm.chat_with_tools()`。模型可能返回一段可见说明和 `search_conversations` 调用。运行时把这些步骤通过 SSE 送到前端。
3. **执行工具并回传。** Runtime 查注册表、检查策略并执行搜索，记录和发送 `tool_result`。在模型上下文中保留上一条 assistant 的工具调用，用 `tool_call_id` 关联工具结果，再请求模型决定下一步。
4. **需要授权时挂起。** 如果模型请求 `rename_conversation`，运行在写操作前进入 `waiting_approval`，前端收到 `approval_required` 并显示审批卡。用户批准或拒绝后，通过新的 SSE 请求继续原来的 run。服务端根据记录重建上下文，批准时重新核对工具定义和当前策略。
5. **提交最终回答。** 模型返回无工具调用的有效文本后，Runtime 保存最终助手消息，把 run 更新为 `completed`，提交后发送 `run_finished`。前端把过程事件放到时间线，把最终回复放到消息区。刷新后可从运行记录回放步骤和恢复待审批卡。

[FastAPI 路由](../backend/app/api/agent.py#L53) · [执行循环](../backend/app/agent/executor.py#L353) · [审批恢复](../backend/app/agent/executor.py#L213) · [前端事件分发](../frontend/src/stores/chat.ts#L371)

**面试官：用户看到的「思考过程」从哪里来？最终回答也是逐字流式吗？**

**候选人：** 页面展示的是执行时间线，包括模型主动给出的阶段性可见文本、工具调用与结果、Skill 加载和待审批状态。模型同时给出可见文本和工具调用时，Runtime 发出 `assistant_text`。普通聊天会逐块发出正文 `delta`。当前「深度回答」按步骤发 SSE，最终正文在 `run_finished` 中一次返回。 [阶段文本和最终答复实现](../backend/app/agent/executor.py#L400) · [普通回复与历史展示链路](../docs/code-reading-guide.md#L88)

**面试官：模型一直在调工具，怎么结束？**

**候选人：** 循环要有明确的终止条件。正常情况是模型给出有效的最终回答，需要审批则挂起，模型请求失败或工具执行状态未知时进入失败路径。项目的循环上限是 **8 轮**，一轮模型响应可以带多个工具调用，因此数据库的步骤数和模型轮数会不同。循环还限制同一工具连续失败次数，避免同一个错误反复消耗时间和额度。 [循环上限与退出处理](../backend/app/agent/executor.py#L67) · [执行器收尾](../backend/app/agent/executor.py#L593)

## 七、用户实际遇到的问题与验证

**面试官：讲一个你们真的遇到过的界面问题。**

**候选人：** 用户在会话 A 发消息，立刻切到会话 B，A 的回复曾经跑到 B。根因是旧 SSE 回调写入了全局消息和流式文本。我们把消息、草稿、工具时间线和发送状态按 `conversation_id` 隔离，发送时绑定自己的会话对象，后续回调只更新那一份。回归测试用一条可控制完成时机的流复现「先切会话，再收到旧回复」。 [项目复盘与回归测试](../docs/chat.md#L200)

**面试官：点了工具审批，页面超时了。刷新后能不能直接再执行一次？**

**候选人：** 先查上次执行到了哪一步。「工具尚未开始」和「工具已经发出、结果未知」需要分开处理。项目检测到后者会停止当前运行，避免循环继续请求同一个动作。对将来可能接入的外部写操作，我会设计稳定的幂等键，并在恢复时查询执行状态。审批本身也要防重复提交，项目通过原子更新记录决策，恢复时复核待执行参数、工具指纹和策略。 [工具超时处理](../backend/app/agent/executor.py#L1238) · [审批决策](../backend/app/agent/executor.py#L1083)

**面试官：用户觉得 Agent 卡住了、刷新后没回答，怎么定位？**

**候选人：** 我先用 `run_id` 找最后一个成功步骤，区分等待模型、工具超时、等待审批和 SSE 中断。开流前的校验错误可以返回普通 HTTP JSON，开流后则通过 SSE 发 `error`。项目在循环被提前关闭时会尝试把仍在运行的 run 标为失败，已提交的步骤可在刷新后回看，最终助手消息在成功收尾时提交。代理缓冲和 SSE 分片也是排查点，可以分别测首事件到达时间，以及把一帧拆块后客户端还能否正确拼接。 [开流前校验](../backend/app/api/agent.py#L53) · [中断收尾](../backend/app/agent/executor.py#L621) · [前端 SSE 测试](../frontend/src/api/agent.test.ts)

**面试官：怎么证明出了问题能查、关键链路能跑？**

**候选人：** 我会分三层验证。用 `FakeLLM` 给 Runtime 固定剧本，覆盖工具成功、参数错误、审批拒绝、超时和步数上限。用 HTTP 模拟传输检查适配器的 URL、请求体、鉴权头和错误映射。最后用真实模型跑一次原生工具调用和审批恢复。这个项目确实遇到过 DeepSeek 返回 `402`，客户端映射成「模型服务余额不足」，该次真实模型验收因此停在模型调用阶段。面试时应把这个结果和自动化测试的结果分别说明。 [FakeLLM](../backend/app/llm/fake.py#L61) · [项目验收记录](../docs/PROJECT_STATUS.md#L9)
