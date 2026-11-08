# 这个项目是怎么跑起来的

> 一页纸讲清三件事：**请求怎么走**、**代码为什么这样分层**、**数据存在哪**。
> 看完这一页，再看 `docs/toolchain.md`（工具怎么用），就够跟上进度了。

## 0. 一句话

**My Agent**：一个带对话界面的 AI 应用。前端 Vue 3 聊天页，后端 FastAPI 提供会话与消息接口，模型调用被抽成 `LLMClient`（默认 `fake` 假实现，配 `LLM_PROVIDER=openai` 即接真实模型），数据落 MySQL——刷新、换浏览器、重启都在。

> 商品 / 分类 / 概览页与它们的后端接口已于 2026-11-08 归档（`archive/product-admin/`），本页只描述当前在跑的部分。

## 1. 全景：谁在跟谁说话

```mermaid
flowchart LR
    subgraph browser["浏览器"]
        UI["Vue 3 SPA<br/>对话页（/chat）"]
    end

    subgraph edge["入口层（两种部署共用一套接口）"]
        DEV["Vite 开发服务器 :5173<br/>/api 代理"]
        NGX["nginx :80<br/>静态文件 + /api 反代"]
    end

    subgraph backend["FastAPI 进程 :8000"]
        direction TB
        API["api/ 接口层<br/>路由 · 参数校验 · 组装响应"]
        SVC["services/ 业务层<br/>事务 · 上下文裁剪 · 错误翻译"]
        LLM["llm/ 模型抽象<br/>fake / OpenAI 兼容"]
        ORM["models/ ORM<br/>表结构映射"]
        API --> SVC
        SVC --> LLM
        SVC --> ORM
    end

    DB[("MySQL 8.4<br/>conversations / messages")]

    UI -->|"/api/..."| DEV
    UI -->|"/api/..."| NGX
    DEV --> API
    NGX --> API
    ORM -->|"SQLAlchemy"| DB
    LLM -->|"HTTPS（openai 模式）"| UP[("模型服务<br/>DeepSeek / OpenAI 兼容")]
```

（图片版：[`images/diagram-architecture.png`](images/diagram-architecture.png)，由本节 mermaid 导出；改图请改上面的代码块，图片只是快照）

**看图记住三件事**：

1. 前端永远只调 `/api/...`，它不知道后端在哪——开发时 Vite 代理转发，部署时 nginx 转发。所以同一份前端代码两种环境都能跑。
2. 后端是**单向分层**：`api → services →（models | llm）`。反过来不行（service 不 import api，model 不 import service）。
3. **模型是外挂的**：`services` 只依赖 `LLMClient` 协议，不关心是假的、DeepSeek 还是别的；换模型不改业务代码，只改 `.env`。

## 2. 一次请求怎么走

以「在对话页发一句话」为例（走流式接口，边生成边显示）：

```mermaid
sequenceDiagram
    autonumber
    participant B as 浏览器
    participant V as Vue（ChatView.vue）
    participant P as 代理（Vite / nginx）
    participant A as api/chat.py
    participant S as services/chat_service.py
    participant L as llm/openai_compatible.py
    participant D as MySQL

    B->>V: 输入「帮我给可乐定价」并回车
    V->>P: POST /api/conversations/{id}/messages/stream
    P->>A: 转发到 127.0.0.1:8000
    A->>S: prepare_stream(db, id, content)
    S->>D: 校验会话存在 + 写入 user 消息（未提交）
    S-->>A: (conversation, user_message, context, is_first)
    A-->>V: 200 text/event-stream（先发 meta 事件）
    S->>L: stream(context)
    L-->>S: 逐块 delta 文本
    S-->>V: data: {"type":"delta","content":"..."}
    S->>D: 全部收完后写入 assistant 消息并提交
    S-->>V: data: {"type":"done",...}
    V-->>B: 逐字渲染，结束后落到完整消息
```

（图片版：[`images/diagram-request.png`](images/diagram-request.png)，由本节 mermaid 导出；改图请改上面的代码块，图片只是快照）

出错了会怎样？

- **开流之前**（会话不存在、内容为空）还是普通 JSON + 400/404，由 `app/main.py` 注册的 5 个异常处理器统一翻译成 `{"code":404,"message":"会话不存在","data":null}`。
- **开流之后**（模型超时、鉴权失败、余额不足）状态码已固定 200，只能发一个 `error` 事件；同时事务回滚，库里不会留下「有提问没回复」的半条对话。
- **客户端中途断开**（关页面、切会话）后端同样回滚。

**前端永远只需要认 `code/message/data` 三个字段**（流式时认事件里的 `type`）。

## 3. 为什么这样分层（每层只干一件事）

| 层 | 目录 | 只负责 | 不负责 | 为什么要有它 |
|---|---|---|---|---|
| 接口层 | `app/api/` | 路由、请求参数、调用 service、包 `Response` / SSE 帧 | 业务规则、SQL、模型细节 | 让 URL 与业务解耦，换路由不影响规则 |
| 数据契约 | `app/schemas/` | 入参出参的字段与校验（Pydantic） | 数据库 | 前端看到的字段与数据库字段不必一样（如时间统一格式化成字符串） |
| 业务层 | `app/services/` | 规则（标题去空白、上下文只带最近 20 条、失败回滚）、事务提交 | HTTP 状态码细节、具体模型厂商 | 同一个规则被多个接口复用时只写一次 |
| 模型抽象 | `app/llm/` | `LLMClient` 协议、fake 与 OpenAI 兼容两种实现、上游错误翻译 | 存库、业务规则 | 换模型 / 加工具调用时不碰业务层 |
| 模型层 | `app/models/` | 表结构（SQLAlchemy） | 业务判断 | 数据库结构的唯一描述，Alembic 据此生成迁移 |
| 公共层 | `app/common/` | 统一响应 `Response`、`BusinessError` 与 5 个处理器 | 具体业务 | 「所有接口长得一样」这件事只实现一次 |

一句话记忆：**api 管门面，schemas 管形状，services 管规矩，llm 管模型，models 管表，common 管统一。**

另有三个装配文件不在上表里：`app/main.py`（创建应用、挂路由、注册 5 个异常处理器与 CORS）、`app/database.py`（Engine、公共 `Base`、`SessionLocal`）、`app/dependencies.py`（`get_db` 为每个请求提供一个 Session）。它们不含业务逻辑，改动风险低但影响面大。

## 4. 数据长什么样

```mermaid
erDiagram
    conversations ||--o{ messages : "一个会话多条消息"
    conversations {
        int id PK "自增主键"
        varchar title "默认「新会话」，首条消息前 30 字自动命名"
        varchar agent_key "默认 default，为多 Agent 预留"
        datetime update_time "有索引，列表按它倒序"
        datetime create_time
    }
    messages {
        int id PK "自增主键"
        int conversation_id FK "ON DELETE CASCADE"
        varchar role "user 或 assistant"
        text content "1-4000 字符"
        varchar model "助手消息记录模型名，可为空"
        datetime create_time
    }
```

（图片版：[`images/diagram-data-model.png`](images/diagram-data-model.png)，由本节 mermaid 导出；改图请改上面的代码块，图片只是快照）

两条真实约束，验收时会碰到：

1. **删会话即删消息**：数据库外键 `ON DELETE CASCADE`，前端不需要逐条删。
2. **上下文只带最近 20 条**：`CONTEXT_LIMIT=20`，system 消息全带；这是成本与连贯性的折中，不是越多越好。

## 5. 代码地图（要改什么去哪）

| 我想做的事 | 改这里 | 顺手要改 |
|---|---|---|
| 加一个接口 | `app/api/chat.py` | `app/schemas/`、`docs/api.md`（契约） |
| 改业务规则 | `app/services/chat_service.py` | `tests/test_chat_service.py` |
| 换模型 / 加模型参数 | `app/llm/`、`app/config.py` | `tests/test_llm.py`、`backend/README.md`「接入真实模型」 |
| 加字段 | `app/models/` → `make revision m="..."` | `app/schemas/`、`docs/api.md` |
| 改页面 | `frontend/src/views/ChatView.vue` | `frontend/src/api/chat.ts`、`utils/markdown.ts` |
| 改样式 | `frontend/src/styles/index.css` + 组件内 `<style scoped>` | — |
| 改部署 | `docker-compose.yml`、两个 `Dockerfile`、`nginx.conf` | `docs/deploy.md` |

## 6. 读代码的顺序（约 40 分钟）

1. `backend/app/main.py`（约 80 行）——应用怎么装起来的
2. `app/api/chat.py` → `app/services/chat_service.py` → `app/models/conversation.py`——顺着一条链路看穿分层
3. `app/llm/base.py` → `app/llm/fake.py` → `app/llm/openai_compatible.py`——模型是怎么被抽象掉的
4. `app/common/response.py` 与 `app/common/exceptions.py`——统一响应与错误是怎么做到的
5. `frontend/src/api/chat.ts` → `views/ChatView.vue`——前端怎么调接口、怎么渲染流式与 Markdown
6. 回到本页第 2 节，把时序图与真实代码对一遍
