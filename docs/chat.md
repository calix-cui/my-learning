# 对话功能设计（阶段 4 · LLM 接入与基础对话）

> 阶段 4 的实施方案。**先设计、后实施**（AGENTS.md §2.3）；确认后按第 8 节的任务顺序逐个交付。
> 阶段依据：[`playbooks/05-development-plan-and-mvp-tasks.md`](playbooks/05-development-plan-and-mvp-tasks.md) 阶段 4。
> 相关决策：[ADR-0006](adr/0006-llm-client-and-chat-storage.md)（落库 + 模型抽象）。

## 1. 目标与边界

**这一阶段要拿到的东西**：用户能在页面上新建会话、发一条消息、收到模型回复；刷新页面后对话还在；会话可以重命名和删除。

**接入方式**（已定，见 PROJECT_STATUS §3.2）：先 `FakeLLM` 打底把链路跑通，再接 OpenAI 兼容 API。默认 `LLM_PROVIDER=fake`，**CI 与本地开发都不需要 key**。

**不做的**（留给后续阶段）：

| 不做 | 留给 |
|---|---|
| 流式 SSE 输出 | 阶段 4 的第二批（T4b），首版同步返回 |
| Tool Calling / function calling | 阶段 6 |
| Agent 执行循环、多轮规划 | 阶段 5 |
| RAG / Memory / 向量库 | 阶段 8 |
| 多 Agent 协作 | 阶段 9；但表结构预留 `agent_key` |
| 鉴权与用户体系 | 暂无排期（当前单用户） |

## 2. 数据模型

```mermaid
erDiagram
    conversations ||--o{ messages : "包含"
    conversations {
        int id PK
        string title "会话标题"
        string agent_key "预留：哪个 agent"
        datetime create_time "创建时间"
        datetime update_time "最后活动时间"
    }
    messages {
        int id PK
        int conversation_id FK
        string role "user / assistant / system"
        text content "消息正文"
        string model "生成该回复的模型"
        datetime create_time
    }
```

| 表 | 字段 | 类型 | 说明 |
|---|---|---|---|
| `conversations` | `title` | `String(100)`，非空，默认「新会话」 | 首次发消息时若仍是默认值，用首条消息前 30 字自动命名 |
| | `agent_key` | `String(50)`，非空，默认 `default` | 现在只有一个 agent；阶段 9 多 Agent 时用来区分 |
| | `update_time` | `DateTime`，非空，`onupdate` | 列表按它倒序，就是「最近聊过」 |
| `messages` | `conversation_id` | 外键 → `conversations.id`，级联删除 | 删会话即删消息 |
| | `role` | `String(16)`，非空 | 只允许 `user` / `assistant` / `system`，服务层校验 |
| | `content` | `Text`，非空 | 用户消息去首尾空白后不能为空（与商品/分类同规则） |
| | `model` | `String(64)`，可空 | 用户消息为 `NULL`；`fake` 时写 `fake` |

- 公共列 `id` / `create_time` 来自 `app/database.py` 的 `Base`，不重复定义。
- 迁移：`alembic revision --autogenerate`，与现有 categories/products 同一套（ADR-0003）。**不用 `create_all`**。
- 索引：`messages.conversation_id`（查询必用）；`conversations.update_time`（列表排序）。

## 3. 接口

全部挂在 `/api` 下，响应仍是统一信封 `{"code":200,"message":"请求成功","data":...}`。

| 方法 | 路径 | 作用 | 主要错误 |
|---|---|---|---|
| `POST` | `/api/conversations` | 新建会话（可带 `title`） | — |
| `GET` | `/api/conversations` | 会话列表，`page` / `page_size`，按 `update_time` 倒序 | 分页参数 422 |
| `GET` | `/api/conversations/{id}` | 会话详情 + 全部消息（按 `id` 升序） | 404「会话不存在」 |
| `PATCH` | `/api/conversations/{id}` | 重命名（`title` 去空白后不能为空） | 404、400「会话标题不能只包含空白」 |
| `DELETE` | `/api/conversations/{id}` | 删除会话及其消息 | 404「会话不存在」 |
| `POST` | `/api/conversations/{id}/messages` | 发一条用户消息，同步返回助手回复 | 404、400「消息内容不能只包含空白」、502/504（模型侧失败） |

发消息的时序（首版同步）：

```mermaid
sequenceDiagram
    participant U as 浏览器
    participant API as api/chat.py
    participant S as services/chat_service.py
    participant L as llm/FakeLLM
    participant DB as MySQL

    U->>API: POST /api/conversations/7/messages
    API->>S: send_message(db, 7, content)
    S->>DB: 查会话（不存在 → 404）
    S->>DB: 插入 user 消息
    S->>DB: 取最近 20 条消息作为上下文
    S->>L: chat(messages)
    L-->>S: LLMReply(content, model)
    S->>DB: 插入 assistant 消息 + 更新会话 update_time
    S-->>API: (user_msg, assistant_msg)
    API-->>U: 200 + 两条消息
```

**上下文策略**：最近 20 条（`system` 始终带上）。超过就截断，不在这里做摘要——摘要属于阶段 8 的 Memory。

## 4. 模型抽象（`app/llm/`）

```python
class LLMReply(TypedDict):
    content: str
    model: str

class LLMClient(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> LLMReply: ...
```

| 文件 | 职责 |
|---|---|
| `app/llm/base.py` | `LLMClient` 协议 + `LLMReply` + `LLMError`（继承 `BusinessError`） |
| `app/llm/fake.py` | `FakeLLM`：固定前缀回显最后一条用户消息；可注入延迟/异常用于测错误分支 |
| `app/llm/openai_compatible.py` | `httpx` 打 `POST {base_url}/chat/completions`，超时映射 504、鉴权/限流映射 502 |
| `app/llm/__init__.py` | `get_llm()` 工厂：按 `settings.llm_provider` 返回实例，作为 FastAPI 依赖注入，测试里 `dependency_overrides` 直接换 |

新增配置（`app/config.py` + `.env.example`）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_PROVIDER` | `fake` | `fake` / `openai` |
| `LLM_BASE_URL` | 空 | 例：`https://api.deepseek.com/v1` |
| `LLM_API_KEY` | 空 | **只从环境注入，不入库、不进镜像** |
| `LLM_MODEL` | 空 | 例：`deepseek-chat` |
| `LLM_TIMEOUT_SECONDS` | `30` | 超时即 504 |

## 5. 错误与状态码

| 情况 | 返回 |
|---|---|
| 会话不存在 | 404 `{"code":404,"message":"会话不存在"}` |
| 消息/标题纯空白 | 400 `{"code":400,"message":"消息内容不能只包含空白"}` |
| 模型鉴权失败、上游 4xx/5xx | 502 `{"code":502,"message":"模型服务不可用"}`（不透传上游原文，避免泄漏 key 与内部信息） |
| 模型超时 | 504 `{"code":504,"message":"模型服务超时"}` |
| 未配置 `LLM_API_KEY` 而 `LLM_PROVIDER=openai` | 启动即失败（`Settings` 校验），不等到第一次请求 |

## 6. 前端页面

新增一个页面 `/chat`，路由与侧边栏同现有三个页面：

```
┌ 会话列表（280px） ┬ 消息区 ─────────────────────┐
│ [+ 新建会话]      │  用户：你好                    │
│ 商品怎么定价      │  助手：我是 fake 模型，收到…    │
│ 昨天的对话        │                               │
│                   ├───────────────────────────────┤
│                   │ [输入框                     ][发送] │
└───────────────────┴───────────────────────────────┘
```

- 进入页面：拉会话列表；有会话则打开最近一条，否则显示空态「开始一个新对话」
- 发送中：输入框与按钮禁用，消息区尾部显示「正在回复…」
- 失败：`ElMessage.error` 显示后端 `message`，用户消息保留、不写入假回复
- 复用现有样式 token 与统计卡之外的表格体系，不新增视觉规范

## 7. 测试口径

| 层 | 覆盖 |
|---|---|
| 后端服务层（内存 SQLite） | 会话 CRUD、级联删除、`role` 校验、空白内容、上下文取最近 20 条、`FakeLLM` 正常/抛错两条路径 |
| 后端接口层（TestClient + `dependency_overrides`） | 6 个端点的成功与 4 类失败（404/400/502/504） |
| 前端 Vitest | `api/chat.ts` 的 6 个函数（URL、参数、错误透传） |
| E2E（可选） | 新建会话 → 发消息 → 刷新仍在 → 重命名 → 删除 |

门槛不变：后端覆盖率 ≥80%，`make check` 与 `pnpm lint && pnpm test && pnpm build` 全绿。

## 8. 任务拆分（每个都能独立验证）

| # | 任务 | 交付 | 验证 |
|---|---|---|---|
| T1 ✅ | 数据模型 + 迁移 | `models/conversation.py`、`models/message.py`、`models/__init__.py`、一个 alembic revision | `make migrate` 后新表存在、`alembic check` 无漂移 |
| T2 ✅ | 模型抽象层 | `app/llm/*`、`config.py` 5 个字段、`.env.example` | 单测：`FakeLLM` 正常/异常；`openai` 用 `httpx.MockTransport` 验 4 种错误映射 |
| T3 ✅ | 会话 CRUD | `schemas/chat.py`、`services/chat_service.py`、`api/chat.py` 的 5 个端点 | 服务层 + 接口层单测、`docs/api.md` 新增一节 |
| T4 ✅ | 发消息（同步） | `POST /messages`、上下文截断、自动命名 | 用 `FakeLLM` 端到端：发 2 条，库里 4 条记录 |
| T4b | 流式输出（SSE） | `GET /messages/stream` + 前端逐字渲染 | 手工验证 + 一条集成测试 |
| T5 | 前端 `/chat` 页面 | `api/chat.ts`、`views/ChatView.vue`、路由与侧边栏 | `pnpm lint/test/build` + 手工三流程 |
| T6 | 文档 | `docs/api.md` §4（含 4.6 发消息）、`docs/how-it-works.md` 架构图补 chat、PROJECT_STATUS 打勾 | 链接检查 0 失效 |

**验收标准**（阶段 4 完成）：本地 `make run` + `pnpm dev` 后，能新建会话、发消息（`FakeLLM` 回复）、刷新后仍在、重命名与删除生效；切 `LLM_PROVIDER=openai` 并配 key 后同流程返回真实模型输出；`make check` 与前端三件套全绿；CI 双 job 绿。

## 9. 风险与取舍

| 风险 | 处理 |
|---|---|
| 同步等待模型，慢时体验差 | 首版设置 30s 超时并明确提示；T4b 换 SSE |
| 上下文无限增长撑爆上下文窗口 | 只取最近 20 条；真正方案在阶段 8 |
| `openai` 兼容层各家字段不同（如 `reasoning_content`） | 只依赖 `choices[0].message.content`；解析失败按 502 处理 |
| 开发机没 key 就无法联调 | 默认 `fake`，CI 永远不依赖外部网络 |
| 消息表增长快 | 现在不分区不归档；数据量成为问题在阶段 11 处理 |
