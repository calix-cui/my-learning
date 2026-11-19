# My Agent · API 契约

> 本文是前后端唯一契约来源。改接口必须同时改这里与代码。
> 示例为 2026-11-08 对 `http://127.0.0.1:8000` 的真实调用；数值随库变化，字段与格式不变。

| 版本 | 日期 | 覆盖 | 维护 |
| --- | --- | --- | --- |
| v2.1 | 2026-11-09 | 账号 7 个操作 + 对话 7 个操作 + 3 个运维/根路径（商品与分类接口已归档） | Python 后端 |

## 1 通用约定

### 1.1 基础地址与路由

- 开发 baseURL：`http://127.0.0.1:8000`；业务接口统一前缀 `/api`；请求/响应为 JSON、UTF-8。
- 账号 7 个操作（`/api/auth`）：`POST /register`、`POST /login`、`POST /logout`、`GET /me`、`GET /sessions`、`DELETE /sessions/{id}`、`POST /password`。
- 对话 7 个操作（`/api/conversations`）：`POST ""`、`GET ""`、`GET /{id}`、`PATCH /{id}`、`DELETE /{id}`、`POST /{id}/messages`（同步）、`POST /{id}/messages/stream`（SSE）。
- **除注册/登录与 3 个运维路径外，所有接口都要求登录**：会话靠 HttpOnly Cookie `my_agent_session` 传递，未登录返回 401（见 3）。
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
| 400 | 业务规则不满足 | `会话标题不能只包含空白`、`消息内容不能为空`、`密码至少 8 位`、`密码最多 72 位`、`原密码不正确` | null |
| 401 | 未登录 / 会话失效 | `请先登录`、`邮箱或密码不正确` | null |
| 403 | 被拒绝 | `注册已关闭`（`ALLOW_REGISTRATION=false`）、`账号已被停用` | null |
| 409 | 冲突 | `该邮箱已注册` | null |
| 404 | 资源不存在 | `会话不存在`、`登录会话不存在`、`Not Found`（未定义路径）；**越权访问他人资源也返回 404**（不暴露存在性） | null |
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

聊天页发送 `execution: "auto"`，使用 [Agent 流式事件](#61-发送消息agent-循环流式)。原有调用方省略 `execution` 或发送 `execution: "text"` 时仍使用下文的文本 SSE 契约。

自动模式请求字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `content` | string | 用户消息，1–4000 字 |
| `execution` | `auto` | 按任务自动选择账号已启用的工具 |
| `reasoning_effort` | `none` / `high` | 默认 `none`，由模型适配器映射，工具权限独立 |
| `skill_mode` | `off` / `manual` / `auto` | 默认 `auto`，单条消息选择与模型按需加载 |
| `skill_keys` | string[] | 本条消息显式选择的来源键，最多 3 项 |
| `skill_catalog_version` | string，可选 | 与当前账号目录快照对齐 |
| `request_id` | UUID，可选 | 同一会话的重复请求返回 409，已有消息可从历史恢复 |

文本模式的传输使用 SSE，保留原有上下文和提交、回滚语义。

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

## 3 账号与鉴权接口（`/api/auth`）

### 3.1 会话机制

- 登录成功由后端 `Set-Cookie: my_agent_session=<opaque>; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000`。库里只存 `SHA-256(token)`，明文 token 只在 Cookie 里。
- 前端**不要**把 token 存 localStorage——JS 读不到这个 Cookie（`document.cookie` 不含它），请求靠浏览器自动携带；开发期走 Vite proxy，同源无跨域问题。
- 有效期 `SESSION_TTL_DAYS`（默认 30 天）滑动续期：距上次刷新超过 1 小时才更新 `last_seen_time` 与过期时间。
- 前端也可以在 `Authorization: Bearer <token>` 里带同一个 token（脚本/测试用），后端优先读 header。

### 3.2 注册 `POST /api/auth/register`

请求：`{"email":"me@example.com","password":"password123","display_name":null}`（`display_name` 可省，≤50 字；密码 8–72 位）。
响应：`200` + `UserResponse`，**同时下发会话 Cookie**（注册即登录）。

```bash
curl -i -X POST http://127.0.0.1:8000/api/auth/register -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"password123"}'
# {"code":200,"message":"请求成功","data":{"id":1,"email":"me@example.com","role":"user",...}}
# set-cookie: my_agent_session=...; HttpOnly; SameSite=lax; Path=/
```

`ALLOW_REGISTRATION=false` 时返回 `403 注册已关闭`；邮箱已存在返回 `409 该邮箱已注册`；邮箱格式非法或密码 <8 位是 `422`。

### 3.3 登录 `POST /api/auth/login`

请求：`{"email":"me@example.com","password":"password123"}`；响应同注册（下发新 Cookie、更新 `last_login_time`）。
密码错 `401 邮箱或密码不正确`；账号被停用 `403 账号已被停用`。

### 3.4 登出 `POST /api/auth/logout`

删除当前会话行并清 Cookie；重复调用仍返回 `200 已退出登录`。

### 3.5 当前用户 `GET /api/auth/me`

返回 `UserResponse`；未登录 `401 请先登录`。前端启动时用它判断登录态，**该请求的 401 不应触发整页跳转**（否则会丢掉 `?redirect=`）。

### 3.6 我的登录设备 `GET /api/auth/sessions` / `DELETE /api/auth/sessions/{id}`

```json
{"items":[{"id":3,"user_agent":"Mozilla/5.0 ...","ip":"127.0.0.1",
           "create_time":"2026-11-09 10:00:00","last_seen_time":"2026-11-09 10:00:00",
           "expires_time":"2026-12-09 10:00:00","is_current":true}]}
```

`is_current` 标出当前浏览器；删别人的会话（含其他用户）返回 `404 登录会话不存在`。

### 3.7 修改密码 `POST /api/auth/password`

请求：`{"old_password":"...","new_password":"..."}`；成功后**只保留当前会话**，其他设备全部失效（需重新登录）。
原密码错 `400 原密码不正确`；新密码不合规 `422`。

### 3.8 修改显示名 `PATCH /api/auth/me`

请求：`{"display_name":"小张"}`；传空串表示清空（界面回落到邮箱）。返回 `UserResponse`。
同一个接口不处理密码——改密码走 3.7。

### 3.9 注销账号 `DELETE /api/auth/me`

请求：`{"password":"..."}`（要再输一次密码，避免误点）。成功后**删除账号及其全部数据**
（会话、消息、设置、登录设备），并清 Cookie；密码错 `400 密码不正确`。

## 4 设置接口（`/api/settings`）

全部需要登录；未登录 `401 请先登录`。

### 4.1 读取模型配置 `GET /api/settings/model`

```json
{"code":200,"message":"请求成功","data":{
  "provider":"openai","base_url":"https://api.deepseek.com/v1","model":"deepseek-chat",
  "timeout_seconds":60,"has_api_key":true,"api_key_hint":"4321",
  "can_store_api_key":true,"inherited_from_env":false,
  "update_time":"2026-11-09 22:40:00"}}
```

- `inherited_from_env=true`：这个账号还没保存过配置，当前用的是服务端环境变量那套。
- `api_key_hint` 只有末四位；**任何接口都不会返回 Key 明文**。
- `can_store_api_key=false`：服务端没配 `APP_SECRET_KEY`，此时只能保存其他字段。

### 4.2 保存模型配置 `PUT /api/settings/model`

```json
{"provider":"openai","base_url":"https://api.deepseek.com/v1","model":"deepseek-chat",
 "timeout_seconds":60,"api_key":"sk-..."}
```

- 只传要改的字段即可。
- `api_key` 三态：**不传** = 保持原值；**空串** = 清除已保存的 Key；**非空** = 加密保存并只留末四位。
- `provider=openai` 时 `base_url` 与 `model` 不能为空（`400`）；`timeout_seconds` 范围 5–300（`422`）。
- 未配置 `APP_SECRET_KEY` 却要保存 Key → `400 服务端未配置 APP_SECRET_KEY，无法保存自定义 Key`。

### 4.3 测试连通性 `POST /api/settings/model/test`

请求字段同 4.2，可以只带本次还没保存的临时值（不落库）。返回：

```json
{"ok":true,"latency_ms":590,"model":"deepseek-flash","message":"连接正常"}
```

失败时 `ok=false`，`message` 是给人看的原因（缺 Key、鉴权失败、限流、余额不足、超时…），
**上游返回的原文不外泄**。

### 4.4 导出数据 `GET /api/settings/export?format=json|markdown`

流式响应，`Content-Disposition` 为 attachment（浏览器直接下载）；只含当前账号的数据，不含 Key 与登录凭据。

- `json`：`{"exported_at","schema":"my-agent.export.v1","user","conversations":[{...,"messages":[...]}]}`
- `markdown`：一级标题 + 账号信息 + 每个会话一节

其他 `format` 取值 → `422`。

### 4.5 读取 / 保存外观 `GET|PUT /api/settings/appearance`

跨设备同步主题用。两个字段都可以是 `null`（表示这个账号没存过）。

```json
{"theme_id":"sand","theme_mode":"dark","update_time":"2026-11-10 15:20:00"}
```

保存只传要改的字段；**显式传 `null` = 清掉该字段**（回到本机偏好），不传 = 保持原值。

- `theme_id`：主题 id（如 `pine` / `sand` / `indigo` / `graphite`），后端不校验取值范围，前端遇到未知 id 会忽略并保留本机主题。
- `theme_mode`：`light` / `dark` / `system`，其他值 `422`。
- 与模型配置共用 `user_settings` 同一行，**只存外观不会让模型配置变成「已配置」**（`inherited_from_env` 仍为 `true`）。

## 5 前端接入注意事项

1. **统一解包**：所有业务响应都是 `{code,message,data}`；axios 拦截器里 `code !== 200` 时抛错并展示 `message`，业务层只拿 `data`。
2. **422 的 `data` 是数组**：不是 `null`，也不是字符串；表单页可读 `data[0].loc` 定位字段，列表页只 toast `message` 即可。
3. **成功也是 HTTP 200**：不要只按 201 判成功；删除成功无数据（`data: null`）。
4. **`create_time` / `update_time` 非 ISO**：形如 `"2026-11-08 22:01:33"`；`new Date(...)` 在 Safari 会 Invalid Date，需先 `s.replace(" ", "T")`。
5. **流式用 `fetch` 而非 `EventSource`**：接口是 `POST` + body（内容可达 4000 字，不能塞 query），前端按 `\n\n` 分帧、`data:` 行 `JSON.parse`，见 `frontend/src/api/chat.ts`。
6. **CORS / 代理**：开发期推荐 Vite proxy（`/api` → `http://127.0.0.1:8000`）；直连时后端已放行 5173/4173（见 1.6），跨域请求需 `withCredentials`。
7. **主题同步规则**：本机 `localStorage` 先保证首屏不闪；登录后拉一次 `/api/settings/appearance`，账号有值就以账号为准，没有就把本机偏好写上去。切换主题时本地立即生效、异步写回账号（失败不影响本地）。
8. **401 统一处理**：`src/api/client.ts` 拦截器收到 401 会清本地登录态并跳 `/login?redirect=...`；`/auth/me` 探测请求带 `skipAuthRedirect: true` 豁免，由路由守卫自行判断。

## 6 Agent 接口（`/api/conversations/{id}/agent`）

聊天页的自动模式和旧 Agent 入口共享执行循环。工具按对话需求调用。审批、工具结果和最终消息可回放。

### 6.1 发送消息（agent 循环，流式）

`POST /api/conversations/{conversation_id}/agent/stream` 是旧 Agent 入口。聊天页使用 §2.7 的自动模式，在相同执行事件上增加正文分片。

| 字段 | 类型 | 说明 |
|---|---|---|
| `content` | string | 用户消息，1–4000 字，纯空白 400 |
| `skill_mode` | `off` / `manual` / `auto` | 默认 manual：读取当前会话挂载；off：禁用 Skill；auto：挂载优先，允许模型按需加载目录中的其他 Skill |

开流前就会拦下的错误（仍是普通 JSON，不是事件流）：

| 情况 | 状态码 | message |
|---|---|---|
| 未登录 | 401 | 请先登录 |
| 会话不存在或不属于自己 | 404 | 会话不存在 |
| 内容全是空白 | 400 | 消息内容不能只包含空白 |
| 同一会话已有运行在跑 | 409 | 这个会话正在生成回复，请稍后再试 |

事件类型（每帧 `data: {json}`）：

| type | 负载 | 含义 |
|---|---|---|
| `run_started` | `run_id`、`conversation_id`、`user_message_id` | 运行开始，用户消息已入库 |
| `skill_loaded` | `seq`、`skill_key`、`name`、`source`、`version` | 指引已加载 |
| `skill_load_failed` | `seq`、`skill_key`、`error_code`、`message` | 加载失败，可继续回答 |
| `skill_resource` | `seq`、`skill_key`、`name`（可空）、`path`、`ok`、`message` | 参考资料读取结果；不推送正文 |
| `assistant_delta` | `content` | 自动模式的正文分片 |
| `assistant_preview_reset` | 无 | 当前轮有工具调用，清除该轮的临时正文 |
| `assistant_text` | `seq`、`content` | 模型「说完这句要调工具」的中间话 |
| `tool_call` | `seq`、`tool`、`args` | 要调哪个工具、参数是什么 |
| `tool_result` | `seq`、`tool`、`ok`、`content`、`duration_ms` | 工具执行结果；失败也是 `ok:false` 的这一步 |
| `run_finished` | `run_id`、`assistant_message_id`、`content`、`steps`、`model` | 助手消息和运行终态提交后推送 |
| `error` | `code`、`message` | 循环中途失败（如模型 502、超过 8 步） |

```
data: {"type":"run_started","run_id":1,"conversation_id":134,"user_message_id":42}

data: {"type":"tool_call","seq":2,"tool":"calculator","args":{"expression":"3**5"}}

data: {"type":"tool_result","seq":3,"tool":"calculator","ok":true,"content":"243","duration_ms":0}

data: {"type":"run_finished","run_id":1,"assistant_message_id":43,"content":"3 的 5 次方等于 243。","steps":4,"model":"deepseek-flash"}
```

三条注意：

1. **中间步骤只进 `agent_steps`，不进 `messages`**——聊天记录里只留「用户问的 + 最终回答」，过程通过下面的接口回放。
2. **步数与时间有硬上限**：最多 8 步、单工具 2 秒、连续 3 次同类失败即中止。
3. **客户端断开会结束运行**：已提交的用户消息和执行步骤可回放，半截助手正文不入库。

### 6.2 查看历史运行

聊天页通过 `GET /api/conversations/{id}?message_limit=50` 读取最近一页消息；追加 `before_message_id` 读更早消息。消息按 ID 升序返回，`next_before_message_id` 为空时到达末页。未传分页参数时仍返回原会话详情。

分页数据中的 `runs` 包含关联本页消息的执行摘要及活跃运行。每条摘要包含 `id`、`user_message_id`、`assistant_message_id`、`status`、`visible_step_count`，以及断线后用来回答「我那条到底发出去了吗、为什么没答复」的三项：`request_id`（客户端提交时的幂等标识，可能为空）、`error_message`（失败原因，来自服务端）、`finished_time`（结束时间，未结束为空）。已完成运行展示在助手消息下，缺少助手消息的未完成运行展示在用户消息下。不再返回 `legacy_runs`；迁移 `b72e80d193ac` 删除两个消息关联均为空的已结束运行及其步骤、审批，保留消息正文、具备任一消息关联的运行和活跃运行。

展开回放时调用 `GET /api/agent/runs/{run_id}/steps`。返回 `data.items`，每条为按 `seq` 排序的工具或 Skill 步骤。他人运行返回 404。

原历史接口继续可用。

`GET /api/conversations/{conversation_id}/agent/runs?limit=5`

返回最近几次运行（含步骤，按 `seq` 升序），用于刷新页面后回放时间线：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "items": [
      {
        "id": 1,
        "status": "completed",
        "step_count": 4,
        "model": "deepseek-flash",
        "started_time": "2026-11-10 23:00:11",
        "finished_time": "2026-11-10 23:00:13",
        "error_message": null,
        "steps": [
          { "seq": 1, "kind": "user_message", "content": "用工具算 3 的 5 次方…" },
          { "seq": 2, "kind": "tool_call", "tool_name": "calculator", "call_id": "call_1", "tool_args": { "expression": "3**5" } },
          { "seq": 3, "kind": "tool_result", "tool_name": "calculator", "call_id": "call_1", "ok": true, "content": "243", "duration_ms": 0 },
          { "seq": 4, "kind": "final_answer", "content": "3 的 5 次方等于 243。" }
        ]
      }
    ]
  }
}
```

`status` 取值：`running` / `completed` / `failed` / `cancelled`（取消暂未实现）。越权同样 404，不暴露会话是否存在。

### 6.2.1 断线后的核对与续查

断流时前端手里可能有两种信息：知道 `run_id`（收到过 `run_started`），或者只知道自己的 `request_id`（连开始事件都没收到）。这两种情况各有一个只读入口，都不重发消息。

`GET /api/agent/runs/{run_id}`：一次请求拿回运行详情——`id`、`conversation_id`、`user_message_id`、`assistant_message_id`、`status`、`step_count`、`model`、`request_id`、`started_time`、`finished_time`、`error_message`、`steps`（按 `seq` 升序）。他人运行 404。

`GET /api/conversations/{conversation_id}/agent/runs?request_id=<uuid>`：按客户端提交时带的 `request_id` 找这次提交。查到返回与上面相同的 `items` 列表（通常一条）；查不到返回 404，`message` 为「这次提交还没有落库，可以重新发送」——这是**唯一可以据此放心重发**的信号。

`GET /api/agent/runs/{run_id}/steps?since_seq=<n>`：增量读取步骤，返回对象而不是数组：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "items": [{ "seq": 3, "kind": "tool_result", "tool_name": "calculator", "ok": true, "content": "243" }],
    "status": "running",
    "visible_step_count": 4,
    "error_message": null,
    "finished_time": null
  }
}
```

`items` 只含 `seq > since_seq` 的可见步骤；`status` / `visible_step_count` 描述整次运行，所以「还在跑吗」和「有没有新步骤」一次请求就能回答。历史页的 `runs[]` 摘要还带 `stop_reason`（`user_cancelled` 表示用户主动终止），用来区分「我停的」和「自己失败的」。

### 6.2.2 挂回正在跑的运行 `GET /api/agent/runs/{run_id}/stream?since_seq=<n>`

执行在服务端继续进行，与发起它的那条连接无关，所以「刷新页面之后回答还在生成」是默认行为，不是特例。这条接口是一个纯读取的 SSE 订阅：

1. 先发一帧 `run_snapshot`，带上当前状态与已经生成的正文（`draft_content`）、可见步骤数、失败原因、终止原因、结束时间——页面一打开就有内容，不用等下一片 token。
2. 运行还没结束就继续推实时事件（`assistant_delta`、步骤、审批、终态），与发送时那条流是同一套事件。
3. 每 15 秒写一行注释心跳 `: ping`：拔网线或合上电脑不会触发断开通知，只有写失败才知道对面还在不在。

```json
{"type":"run_snapshot","run_id":52,"conversation_id":336,"status":"running",
 "draft_content":"雨水打在窗上","visible_step_count":2,
 "error_message":null,"stop_reason":null,"finished_time":null}
```

`since_seq` 用于跳过已读过的步骤事件。多个页面（两个标签页、手机 + 电脑）可以同时订阅同一次运行，彼此不影响。

### 6.2.3 终止与重新生成

`POST /api/agent/runs/{run_id}/stop`：只有用户点「停止」才该调它。运行已结束返回 409「这次运行已经结束」；成功返回 `{"run_id": 52, "status": "cancelled"}`。已经生成的部分会落成一条正常的助手消息（不是半截草稿），`status=cancelled`、`stop_reason=user_cancelled`，所以刷新、换设备都能看到它停在哪里。

`POST /api/agent/runs/{run_id}/regenerate`：用**同一条提问**重跑，流式响应。旧的问答会被删掉（用户要求「直接删除旧回答，完全开始新回答」），然后把 `run_snapshot` 与实时事件按上面那套格式推回来。运行还没结束返回 409「这次运行还没结束，先终止再重新生成」。

断开连接、关标签页、刷新页面都**不会**终止运行；无人订阅满 10 分钟后服务端才自行停止，并记 `stop_reason=abandoned`、`error_message="长时间没有客户端接收，已停止"`。

### 6.3 内置工具（只读）

| 工具 | 参数 | 说明 |
|---|---|---|
| `calculator` | `expression` | 四则/幂/括号，`^` 按幂处理（模型爱写 `3^5`）；拒绝 `__import__`、`9**9**9` 这类越界表达式 |
| `now` | `timezone?` | 当前时间，默认 `Asia/Shanghai`，输出「2026-11-10 22:55:38 CST（星期二）」 |
| `search_conversations` | `keyword`、`limit?` （1–10） | 在自己历史会话标题里检索，只返回自己的数据 |
| `rename_conversation` | `title`、`conversation_id?` | **写工具**，必须用户批准才执行；省略 `conversation_id` 表示当前会话 |

### 6.4 工具治理与审批

写操作（`level=write`）不会直接执行：执行器把 run 置为 `waiting_approval`，把这次调用写成一行 `agent_approvals(pending)`，事件流吐出 `approval_required` 后**结束这一帧**。用户点批准或拒绝后调决策接口，服务端从 `agent_steps` 重放上下文，用同一个循环接着跑。

`GET /api/settings/tools`

```json
{ "code": 200, "message": "请求成功", "data": {
  "items": [
    { "name": "rename_conversation", "description": "把一个会话改名…", "level": "write",
      "enabled": true, "requires_approval": true, "calls_today": 2 }
  ],
  "daily_tool_budget": 500, "used_today": 2 } }
```

关掉的工具仍在清单里（`enabled=false`），只是注册表不再向模型暴露、也执行不了——这样用户还能再打开。

**这个接口不建立 MCP 连接**：远端 MCP 服务器（HTTP/SSE）握手常常几秒起步，打开设置页不该等它。展示路径只复用进程里已经建立的连接（`registry_for(..., connect=False)`），没连过的服务器这次就不出现，`last_status` 也不改；要探测请用 MCP 页的「测试连接」，或者等一次对话跑起来。`PUT` 校验未知工具名时，上一进程留下的禁用名单也算已知，避免连不上时保存被挡。

`PUT /api/settings/tools`：`{ "disabled": ["calculator"], "daily_tool_budget": 300 }`，未知工具名返回 400。

`GET /api/settings/tools/stats?days=7`：`{ "days": 7, "items": [{"tool_name":"calculator","calls":12,"failures":0}], "total": 12 }`。

`GET /api/agent/runs/{run_id}/approvals`：返回这次运行的全部审批（`status` 为 `pending|approved|rejected|expired`）。越权 404。

`POST /api/agent/runs/{run_id}/approvals/{approval_id}`：`{ "decision": "approve" }` 或 `{ "decision": "reject", "note": "标题我自己改" }`。成功时返回 **SSE 流**（和 `/agent/stream` 同一套事件，开头直接是 `tool_result`）；审批已决定或 run 不处于等待态返回 409，开流前的错误仍是普通 JSON。

限制：单次运行最多 5 次审批、同一工具被拒 2 次后本次运行直接失败（403）；每天所有工具调用合计不超过 `daily_tool_budget`。

### 6.5 MCP 工具市场（`/api/mcp`）

接进来的 MCP 工具**不新开接口**：它们出现在 `GET /api/settings/tools` 里，`source="mcp"`、名字是 `mcp__{slug}__{tool}`、级别是 `external`（服务器标了只读才是 `read`）。开关、每日预算、审批、时间线全都复用阶段 6 那一套。

`GET /api/mcp/catalog`：内置清单 + 每个条目是否已接入。

```json
{ "code": 200, "message": "请求成功", "data": {
  "items": [
    { "slug": "filesystem", "display_name": "文件系统", "summary": "读写你指定的目录…",
      "transport": "stdio", "tags": ["本地", "文件"], "requires_path": true,
      "installed_id": null, "last_status": null, "updated": "2026-11" }
  ],
  "updated": "2026-11" } }
```

`GET /api/mcp/servers`：已接入的服务器。`tools` 只在**当前有连接**时才有内容（不为了展示去连一次服务器），`env_keys` 只给键名。

`POST /api/mcp/servers`：接入。内置条目只要 `{ "slug": "filesystem", "path": "/Users/me/repo" }`；自定义条目补齐 `display_name` / `transport` / `command`+`args`（stdio）或 `url`（http）。`env` 会加密入库，接口从不明文回显。重复 slug 400，缺 path 400，命令不在白名单 400，http 指向内网 400。

`PATCH /api/mcp/servers/{id}`：`{ "enabled": false }` 启停，或改 `display_name` / `args` / `url` / `env`。改完会**断开旧连接**，下次运行重新连。

`DELETE /api/mcp/servers/{id}`：移除并关连接。

`POST /api/mcp/servers/{id}/test`：立即连一次、列一次工具、立刻关掉，返回 `{ "ok": true, "message": "连接成功，发现 2 个工具", "tools": [...], "duration_ms": 1240 }`，同时把 `last_status` / `tool_count` / `last_connected_time` 落库。

失败语义：连不上不会让对话失败——`registry_for()` 只记 `last_status=error` 与 `last_error` 并跳过这台服务器，模型继续用剩下的工具回答。

### 6.6 Skill（`/api/skills`）

现行聊天的 Skill 来自后端本地目录，按账号保存目录快照。安装和限制见 [Skill 文档](skills.md)。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/skills/catalog` | 当前账号元数据快照，空缓存时初始化 |
| POST | `/api/skills/catalog/rescan` | 登录、刷新和设置页使用的扫描入口 |
| GET | `/api/skills/catalog/detail?key=&version=` | 按稳定来源键加载只读正文 |

目录响应包含 `items`、`version`。每项包含 `key`、`slug`、`name`、`description`、`source`、`trust`、`version`、`tools` 和 `icon`。目录响应只包含元数据。

自动聊天请求可附 `skill_keys`（最多 3 项）和 `skill_catalog_version`，默认 `skill_mode: "auto"`。显式选择只用于当前消息；`manual` 只加载显式选择项，`off` 关闭 Skill。`auto` 还允许模型按元数据选择。旧 `skill_slug` 不参与新聊天的选择。

未知或越权的 Skill 键返回 400，过期目录版本返回 409。按需读取已变更的文件返回 404 或 409。目录扫描失败保留原快照。

旧版 `GET /skills`、`GET /skills/{slug}`、数据库写接口与 `GET /skills/legacy/export` 已随 `skills` 表一起删除（迁移 `d39c4a07e1f2`，2026-11-19）。会话挂载仍是 `PUT /conversations/{id}/skill`，只接受本地目录里存在的 slug。

## 附录 A：数据模型（`users` / `sessions` / `user_settings` / `conversations` / `messages` / `agent_runs` / `agent_steps` / `agent_approvals`）

```
users
  id              int  pk
  email           varchar(255)  unique
  password_hash   varchar(255)  Argon2id
  display_name    varchar(50)   nullable
  role            varchar(20)   默认 user（admin 用脚本建）
  is_active       tinyint(1)    默认 1
  last_login_time datetime     nullable
  create_time     datetime

sessions
  id              int  pk
  user_id         int  FK → users.id ON DELETE CASCADE，有索引
  token_hash      varchar(64)  unique（sha256(token)）
  user_agent      varchar(255) nullable
  ip              varchar(64)  nullable
  last_seen_time  datetime
  expires_time    datetime     有索引
  create_time     datetime

user_settings
  id                        int  pk
  user_id                   int  FK → users.id ON DELETE CASCADE，unique
  tools_disabled            json          默认 []
  daily_tool_budget         int           默认 500
  model_provider            varchar(20)   默认 fake
  theme_id                  varchar(32)   nullable（主题 id，如 pine/sand）
  theme_mode                varchar(10)   nullable（light/dark/system）
  model_base_url            varchar(255)  nullable
  model_name                varchar(64)   nullable
  model_timeout_seconds     int           默认 30
  model_api_key_ciphertext  varchar(512)  nullable（Fernet 密文）
  model_api_key_hint        varchar(8)    nullable（末四位）
  skill_catalog             json          nullable，账号级本地 Skill 元数据快照
  model_configured          tinyint(1)    默认 0（只有真配过模型才置 1）
  create_time / update_time datetime

conversations
  id            int  pk autoincrement
  user_id       int  FK → users.id ON DELETE CASCADE，有索引（数据隔离唯一维度）
  title         varchar(100)  默认「新会话」
  agent_key     varchar(50)   默认 default（为多 Agent 预留）
  skill_slug    varchar(32)   nullable（挂着的技能，内置或自建的 slug）
  update_time   datetime      有索引，列表按它倒序
  create_time   datetime

messages
  id               int  pk autoincrement
  conversation_id  int  FK → conversations.id  ON DELETE CASCADE，有索引
  role             varchar(16)   user | assistant
  content          text
  model            varchar(64)   nullable
  create_time      datetime

agent_runs
  id               int  pk autoincrement
  conversation_id  int  FK → conversations.id  ON DELETE CASCADE，有索引
  user_id          int  FK → users.id          ON DELETE CASCADE，有索引
  user_message_id  int          nullable FK → messages.id ON DELETE SET NULL，有索引
  assistant_message_id int      nullable FK → messages.id ON DELETE SET NULL，唯一索引
  status           varchar(16)  running | waiting_approval | completed | failed | cancelled
  step_count       int          默认 0
  model            varchar(64)  nullable（这一轮实际回话的模型）
  started_time     datetime
  finished_time    datetime     nullable
  error_message    varchar(255) nullable

agent_steps
  id           int  pk autoincrement
  run_id       int  FK → agent_runs.id  ON DELETE CASCADE，有索引
  seq          int            第几步，从 1 开始；与 run_id 组成唯一键
  kind         varchar(20)    user_message | assistant_text | tool_call | tool_result | final_answer
  content      text           nullable
  tool_name    varchar(64)    nullable
  call_id      varchar(64)    nullable；模型给的调用标识，结果靠它配对而不是靠名字
  tool_args    json           nullable
  ok           tinyint(1)     nullable（仅工具步骤有值）
  duration_ms  int            nullable
  create_time  datetime

agent_approvals
  id           int  pk autoincrement
  run_id       int  FK → agent_runs.id  ON DELETE CASCADE，有索引
  user_id      int  FK → users.id       ON DELETE CASCADE，有索引
  seq          int            对应哪一步 tool_call
  tool_name    varchar(64)
  tool_args    json           nullable（原样回放给用户看）
  status       varchar(16)    pending | approved | rejected | expired
  note         varchar(200)   nullable（拒绝理由）
  decided_time datetime       nullable
  create_time  datetime
```

审批不设过期时间：写操作挂多久都等用户决定，避免「去泡杯咖啡回来发现要重跑」。真正约束的是次数（单 run ≤5 次审批、同工具被拒 ≤2 次），以及 30 天仍未决定的记录由清理任务标 `expired`。

`agent_steps` 是「过程」，`messages` 是「对话」：一次运行只把最终答复写进 `messages`，中间的工具往返全留在 `agent_steps`，这样聊天记录不会被工具日志污染，又能在需要时完整回放。

删会话即删该会话全部消息（`ON DELETE CASCADE`），前端不需要逐条删；`messages` 不冗余 `user_id`，归属通过会话间接确定。

`skills` 表已于 2026-11-19 删除（迁移 `d39c4a07e1f2`）：技能只剩文件一种来源，不再有数据库写入路径。`conversations.skill_slug` 仍保留，指向本地目录里的包。

## 附录 B：本地起服务与自检

- 起服务：项目根 `./scripts/dev.sh`（推荐）或 `cd backend && make run` + `cd frontend && pnpm dev`。
- 自检：`cd backend && make check`；`cd frontend && pnpm lint && pnpm test && pnpm build`。
- 端到端（需前后端在跑）：`cd frontend && pnpm acceptance:chat`（对话流）、`pnpm acceptance:agent`（深度回答与工具时间线）、`pnpm acceptance:auth`（注册→登录→刷新→退出→再登录）、`pnpm acceptance:settings`（模型设置→测试连接→改显示名→导出→注销）、`pnpm acceptance:tools`（工具启停→审批拒绝→审批批准→刷新复原）、`pnpm acceptance:mcp`（市场接入→试连→审批整链路）、`pnpm acceptance:skills`（内置只读→选择→挂载→卸载）。
- 第一个管理员：`cd backend && ADMIN_EMAIL=... ADMIN_PASSWORD='至少8位' uv run python -m app.create_admin`（存在则重置密码并升权）。


### Skill 运行记录补充（2026-11-14）

`GET /api/conversations/{id}/agent/runs` 的步骤增加可空 `skill_key`、`skill_name`、`skill_source`、`skill_version`；`kind` 支持 `skill_loaded`、`skill_load_failed`、`skill_resource`。资源步骤用 `ok` 表示结果、`tool_args.path` 保存相对路径、`content` 保存可读摘要。资源正文只保存于运行快照并进入模型上下文，不在 SSE 或运行列表中返回。

模型通过 Runtime 控制动作 `__runtime_read_skill_resource({skill_key,path})` 请求读取；它不是业务 Tool 或独立 HTTP API。仅接受本次已加载 Skill 清单中的资源。与普通工具同批请求时，普通工具返回未执行，待模型读取指引后重新规划；原工具权限和审批策略不变。
