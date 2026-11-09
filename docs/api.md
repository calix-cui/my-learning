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

## 5 前端接入注意事项

1. **统一解包**：所有业务响应都是 `{code,message,data}`；axios 拦截器里 `code !== 200` 时抛错并展示 `message`，业务层只拿 `data`。
2. **422 的 `data` 是数组**：不是 `null`，也不是字符串；表单页可读 `data[0].loc` 定位字段，列表页只 toast `message` 即可。
3. **成功也是 HTTP 200**：不要只按 201 判成功；删除成功无数据（`data: null`）。
4. **`create_time` / `update_time` 非 ISO**：形如 `"2026-11-08 22:01:33"`；`new Date(...)` 在 Safari 会 Invalid Date，需先 `s.replace(" ", "T")`。
5. **流式用 `fetch` 而非 `EventSource`**：接口是 `POST` + body（内容可达 4000 字，不能塞 query），前端按 `\n\n` 分帧、`data:` 行 `JSON.parse`，见 `frontend/src/api/chat.ts`。
6. **CORS / 代理**：开发期推荐 Vite proxy（`/api` → `http://127.0.0.1:8000`）；直连时后端已放行 5173/4173（见 1.6），跨域请求需 `withCredentials`。
7. **401 统一处理**：`src/api/client.ts` 拦截器收到 401 会清本地登录态并跳 `/login?redirect=...`；`/auth/me` 探测请求带 `skipAuthRedirect: true` 豁免，由路由守卫自行判断。

## 附录 A：数据模型（`users` / `sessions` / `user_settings` / `conversations` / `messages`）

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
  model_provider            varchar(20)   默认 fake
  model_base_url            varchar(255)  nullable
  model_name                varchar(64)   nullable
  model_timeout_seconds     int           默认 30
  model_api_key_ciphertext  varchar(512)  nullable（Fernet 密文）
  model_api_key_hint        varchar(8)    nullable（末四位）
  create_time / update_time datetime

conversations
  id            int  pk autoincrement
  user_id       int  FK → users.id ON DELETE CASCADE，有索引（数据隔离唯一维度）
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

删会话即删该会话全部消息（`ON DELETE CASCADE`），前端不需要逐条删；`messages` 不冗余 `user_id`，归属通过会话间接确定。

## 附录 B：本地起服务与自检

- 起服务：项目根 `./scripts/dev.sh`（推荐）或 `cd backend && make run` + `cd frontend && pnpm dev`。
- 自检：`cd backend && make check`；`cd frontend && pnpm lint && pnpm test && pnpm build`。
- 端到端（需前后端在跑）：`cd frontend && pnpm acceptance:chat`（对话流）、`pnpm acceptance:auth`（注册→登录→刷新→退出→再登录）、`pnpm acceptance:settings`（模型设置→测试连接→改显示名→导出→注销）。
- 第一个管理员：`cd backend && ADMIN_EMAIL=... ADMIN_PASSWORD='至少8位' uv run python -m app.create_admin`（存在则重置密码并升权）。
