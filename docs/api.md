# My Agent · API 契约

> 本文是前后端唯一契约来源。改接口必须同时改这里与代码。
> 示例为 2026-11-08 对 `http://127.0.0.1:8000` 的真实调用；数值随库变化，字段与格式不变。

| 版本 | 日期 | 覆盖 | 维护 |
| --- | --- | --- | --- |
| v2.0 | 2026-11-08 | 对话 7 个操作 + 3 个运维/根路径（商品与分类接口已归档） | Python 后端 |

## 1 通用约定

### 1.1 基础地址与路由

- 开发 baseURL：`http://127.0.0.1:8000`；业务接口统一前缀 `/api`；请求/响应为 JSON、UTF-8。
- 对话 7 个操作（`/api/conversations`）：`POST ""`、`GET ""`、`GET /{id}`、`PATCH /{id}`、`DELETE /{id}`、`POST /{id}/messages`（同步）、`POST /{id}/messages/stream`（SSE）。
- 运维 3 个路径（无 `/api` 前缀、裸 JSON）：`GET /`、`GET /healthz`、`GET /readyz`。
- 商品 / 分类接口已随商品管理模块归档（`archive/product-admin/`），旧契约见 `archive/product-admin/docs/api-product-admin.md`。
- 交互式文档：`/docs`（Swagger UI）、`/redoc`、机器可读 `/openapi.json`。
- 示例中的 ID/数值仅为演示，实际调用请替换为库中真实值。

### 1.2 统一响应结构

成功（除根路径与探针外，所有接口都套此壳）：

```json
{"code":200,"message":"请求成功","data":{}}
```

失败：`{"code":<HTTP状态码>,"message":"中文原因","data":null}`。
**例外：422 的 `data` 是 pydantic 错误明细数组，不是 null**——前端默认只展示 `message`，表单可读 `data[0].loc` 定位字段：

```json
{"code":422,"message":"请求参数校验失败","data":[{"type":"greater_than_equal","loc":["query","page"],"msg":"Input should be greater than or equal to 1","input":"0","ctx":{"ge":1}}]}
```

- `code` 与 HTTP 状态码一致；**成功一律 HTTP 200**（新增不是 201）；无返回值的操作 `data` 为 `null`。
- 只有 `GET /`、`/healthz`、`/readyz` 返回裸 JSON，其余接口都套统一外壳。

### 1.3 错误码表

| HTTP/code | 含义 | 真实文案 | data |
| --- | --- | --- | --- |
| 400 | 业务规则不满足 | `会话标题不能只包含空白`、`消息内容不能为空` | null |
| 404 | 资源不存在 | `会话不存在`、`Not Found`（未定义路径） | null |
| 422 | 参数校验失败 | `请求参数校验失败`（缺字段、类型错、`page<1`、`page_size>100`、`content` 超 4000 字、路径 ID 非整数） | 明细数组 |
| 502 | 上游模型出错 | `模型服务鉴权失败，请检查 LLM_API_KEY`、`模型服务余额不足，请检查账户余额`、`模型服务限流，请稍后重试`、`模型服务不可用`、`模型返回格式无法解析`、`模型返回内容为空`（见 4.6） | null |
| 504 | 上游超时 | `模型服务超时`（默认 30s，见 `LLM_TIMEOUT_SECONDS`） | null |
| 500 | 服务端错误 | `数据库操作失败，请检查记录后重试`、`服务器内部错误`；服务层包装：`查询会话失败，请稍后重试` 等 | null |
| 503 | 依赖不可用 | 仅 `/readyz`：数据库连不上时返回裸 JSON `{"status":"unavailable","database":"down"}` | 裸 JSON |

### 1.4 字段类型与格式

| 字段 | 类型 | 格式 / 约束 |
| --- | --- | --- |
| `id` / `conversation_id` | int | 正整数；路径参数必须 > 0 |
| `title` | str | 1–100 字符；省略或纯空白 → `新会话`，首尾空白 `strip` |
| `role` | str | `user` / `assistant` |
| `content` | str | 1–4000 字符（超过 → 422），首尾空白 `strip`，纯空白 → 400 |
| `model` | str \| null | 助手消息才有；用户消息为 `null` |
| `create_time` / `update_time` | **str** | `YYYY-MM-DD HH:mm:ss`，**非 ISO 8601、无时区** |

### 1.5 路径与分页参数

- 路径 ID 非正整数 → 422（`loc: ["path", ...]`）；未定义路径 → 404 `Not Found`。
- 分页（`GET /api/conversations`）：`page` ≥1 默认 1、`page_size` 1–100 默认 10；按 `update_time` 倒序，同秒内按 `id` 倒序。
- 非法查询参数（`page=0`、`page_size=101`）→ 422，`loc` 指向 `query`。

### 1.6 CORS（跨域）

`app/main.py` 放行 4 个来源：`http://localhost:5173`、`http://127.0.0.1:5173`、`http://localhost:4173`、`http://127.0.0.1:4173`；`allow_credentials=False`，方法与请求头为 `*`。
预检 `OPTIONS` 由中间件直接返回 200：`access-control-allow-origin: <请求的 Origin>`、`access-control-max-age: 600`；非白名单 Origin 不返回 ACAO 头（浏览器拦截）。前端走 Vite proxy 时同源，不涉及 CORS。

### 1.7 根路径与运维探针（裸 JSON，无外壳）

| 方法 | 路径 | 成功响应 | 说明 |
| --- | --- | --- | --- |
| GET | `/` | `{"message":"FastAPI服务正在运行中"}` | 手动探活 |
| GET | `/healthz` | `{"status":"ok"}` | 存活探针，不碰数据库 |
| GET | `/readyz` | `{"status":"ready","database":"up"}` | 就绪探针，执行 `SELECT 1`；失败返回 503（见表 1.3） |

## 2 对话接口（`/api/conversations`）

阶段 4 新增：会话与消息都落库，刷新后仍在；首版同步返回模型回复（流式见 T4b）。
本节会话 CRUD，4.6 是发消息（同步调用模型）。

### 2.1 新建会话 `POST /api/conversations`

请求体（`title` 可省略）：

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 否 | ≤100 | 省略或纯空白 → `新会话`；首尾空白会被去掉 |

```json
{"title":"  定价讨论  "}
```

响应 `data`：`id`、`title`（已 `strip`）、`agent_key`（固定 `default`）、`update_time`、`create_time`。

```json
{"id":1,"title":"定价讨论","agent_key":"default","update_time":"2026-11-07 23:25:40","create_time":"2026-11-07 23:25:40"}
```

### 2.2 会话列表 `GET /api/conversations`

查询参数：`page`（默认 1，≥1）、`page_size`（默认 10，1–100）。
排序：`update_time` 倒序，同秒内按 `id` 倒序（新建的会话一定在最前）。

`data` 是分页结构，多一个 `message_count`（该会话消息条数，用一次聚合查询算出，不产生 N+1）：

```json
{"items":[{"id":2,"title":"新会话","agent_key":"default","update_time":"2026-11-07 23:25:40","create_time":"2026-11-07 23:25:40","message_count":0}],"total":1,"page":1,"page_size":10}
```

### 2.3 会话详情 `GET /api/conversations/{id}`

`data` 在会话字段外多一个 `messages`，按发送顺序（`id` 升序）排列；用户消息的 `model` 为 `null`。

```json
{"id":1,"title":"改名后","agent_key":"default","update_time":"2026-11-07 23:25:40","create_time":"2026-11-07 23:25:40","messages":[{"id":1,"conversation_id":1,"role":"user","content":"你好","model":null,"create_time":"2026-11-07 23:25:41"}]}
```

空会话返回 `"messages": []`；不存在返回 404 `会话不存在`。

### 2.4 重命名会话 `PATCH /api/conversations/{id}`

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `title` | string | 是 | 1–100；去首尾空白后不能为空 |

- `""` → 422（schema 的 `min_length=1`）
- `"   "` → 400 `会话标题不能只包含空白`（service 层判断）
- id 不存在时**优先**返回 404，不再看标题是否合法

### 2.5 删除会话 `DELETE /api/conversations/{id}`

删除会话及其全部消息（数据库外键 `ON DELETE CASCADE` + ORM `cascade="all, delete-orphan"`）。成功返回 `data: null`；不存在返回 404。

### 2.6 发送消息 `POST /api/conversations/{id}/messages`

请求体：

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | 1–4000 | 去首尾空白后不能为空 |

行为：

1. 会话不存在 → 404（**先于**内容校验）；内容纯空白 → 400。
2. 用户消息与助手回复在**同一个事务**里提交，模型失败整体回滚，库里不留半条对话。
3. 上下文 = 该会话所有 `system` 消息 + 最近 20 条非 system 消息（含本次提问）。
4. 会话标题仍是 `新会话` 且这是第一条消息时，用本次内容前 30 字自动命名。
5. 会话 `update_time` 刷新，所以发完消息它在列表里排到最前。

响应 `data` 同时给两条消息，前端不必再查详情：

```json
{"user_message":{"id":1,"conversation_id":3,"role":"user","content":"帮我给可乐定价","model":null,"create_time":"2026-11-07 23:35:14"},"assistant_message":{"id":2,"conversation_id":3,"role":"assistant","content":"[fake] 收到：帮我给可乐定价","model":"fake","create_time":"2026-11-07 23:35:14"}}
```

模型由 `LLM_PROVIDER` 决定（默认 `fake`，回显形如 `[fake] 收到：<你的话>`；接真实模型见 `backend/README.md`「接入真实模型」）。上游故障映射见下表：

| 场景 | HTTP/code | 文案 |
| --- | --- | --- |
| 鉴权失败（401/403） | 502 | `模型服务鉴权失败，请检查 LLM_API_KEY` |
| 余额不足（402） | 502 | `模型服务余额不足，请检查账户余额` |
| 限流（429） | 502 | `模型服务限流，请稍后重试` |
| 其他上游 4xx/5xx | 502 | `模型服务不可用` |
| 返回体不是预期 JSON / 无 content | 502 | `模型返回格式无法解析` / `模型返回内容为空` |
| 超时（默认 30s） | 504 | `模型服务超时` |
| 流式中途失败 | SSE `error` 事件 | 同上表文案，状态码固定在事件里 |

上游的原始报错不会透传给前端，只进服务端日志。

### 2.7 发送消息（流式）`POST /api/conversations/{id}/messages/stream`

与 4.6 的区别只在传输方式：回复按 SSE 逐块吐出，适合前端做「逐字渲染」。请求体、校验规则、上下文窗口、事务语义与 4.6 完全一致。

**为什么是 POST 而不是 GET**：设计稿里写的是 `GET .../messages/stream?content=...`，但消息最长 4000 字，塞进 query string 既可能超长、也会整段进访问日志，所以改为 POST + 请求体；代价是前端不能用原生 `EventSource`（只支持 GET），改用 `fetch` + `ReadableStream` 解析。

响应头：`Content-Type: text/event-stream`、`Cache-Control: no-cache`、`X-Accel-Buffering: no`（后者防 nginx 缓冲，否则 delta 会被攒到最后一次性吐出）。

每帧一行的 `data:` JSON，四种事件：

| `type` | 时机 | 负载 |
| --- | --- | --- |
| `meta` | 开始 | `user_message`（用户消息已落库，带 id） |
| `delta` | 每块 | `content`（增量文本，可能只有几个字） |
| `done` | 结束 | `conversation_id`、`conversation_title`、`message_count`、`assistant_message` |
| `error` | 失败 | `code`、`message`（502/504/500） |

```
data: {"type": "meta", "user_message": {...}}

data: {"type": "delta", "content": "[fak"}

data: {"type": "done", "conversation_id": 3, "conversation_title": "流式测试", "message_count": 2, "assistant_message": {...}}
```

注意三点：

1. **校验错误仍是普通 JSON**（400/404），发生在开流之前，所以前端要先判 `response.ok`。
2. **开始流式后状态码固定为 200**，模型出错只能以 `error` 事件告知，此时后端已回滚，库里不留半条对话。
3. 客户端中途断开（关页面、切会话）后端同样回滚，不会留下「只有提问没有回复」的记录。

## 3 前端接入注意事项

1. **统一解包**：所有业务响应都是 `{code,message,data}`；axios 拦截器里 `code !== 200` 时抛错并展示 `message`，业务层只拿 `data`。
2. **422 的 `data` 是数组**：不是 `null`，也不是字符串；表单页可读 `data[0].loc` 定位字段，列表页只 toast `message` 即可。
3. **成功也是 HTTP 200**：不要只按 201 判成功；删除成功无数据（`data: null`）。
4. **`create_time` / `update_time` 非 ISO**：形如 `"2026-11-08 22:01:33"`；`new Date(...)` 在 Safari 会 Invalid Date，需先 `s.replace(" ", "T")`。
5. **流式用 `fetch` 而非 `EventSource`**：接口是 `POST` + body（内容可达 4000 字，不能塞 query），前端按 `\n\n` 分帧、`data:` 行 `JSON.parse`，见 `frontend/src/api/chat.ts`。
6. **CORS / 代理**：开发期推荐 Vite proxy（`/api` → `http://127.0.0.1:8000`）；直连时后端已放行 5173/4173（见 1.6）。

## 附录 A：数据模型（`conversations` / `messages`）

```
conversations
  id            int  pk autoincrement
  title         varchar(100)  默认「新会话」
  agent_key     varchar(50)   默认 default（为多 Agent 预留）
  update_time   datetime      有索引，列表按它倒序
  create_time   datetime

messages
  id               int  pk autoincrement
  conversation_id  int  FK → conversations.id  ON DELETE CASCADE，有索引
  role             varchar(16)   user | assistant
  content          text
  model            varchar(64)   nullable
  create_time      datetime
```

删会话即删该会话全部消息（数据库外键 `ON DELETE CASCADE`），前端不需要逐条删。

## 附录 B：本地起服务与自检

- 起服务：项目根 `./scripts/dev.sh`（推荐）或 `cd backend && make run` + `cd frontend && pnpm dev`。
- 自检：`cd backend && make check`；`cd frontend && pnpm lint && pnpm test && pnpm build`。
- 端到端：`cd frontend && pnpm acceptance:chat`（需前后端在跑，会清空会话）。
