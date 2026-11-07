# 商品管理网站 · API 契约

> 本文是前后端唯一契约来源。改接口必须同时改这里与代码。
> 示例为 2026-11-07 对 `http://127.0.0.1:8000` 的真实调用；数值随库变化，字段与格式不变。

| 版本 | 日期 | 覆盖 | 维护 |
| --- | --- | --- | --- |
| v1.1 | 2026-11-07 | 11 个业务操作 + 3 个运维/根路径 | Python 后端 |

## 1 通用约定

### 1.1 基础地址与路由

- 开发 baseURL：`http://127.0.0.1:8000`；业务接口统一前缀 `/api`；请求/响应为 JSON、UTF-8。
- 商品 6 个操作（`/api/products`）：`POST ""`、`GET ""`、`GET /count`、`GET /{id}`、`PATCH /{id}`、`DELETE /{id}`。
- 分类 5 个操作（`/api/categories`）：`POST ""`、`GET ""`、`PATCH /{id}`、`DELETE /{id}`、`GET /statistics`。
- 对话 5 个操作（`/api/conversations`）：`POST ""`、`GET ""`、`GET /{id}`、`PATCH /{id}`、`DELETE /{id}`（发消息由阶段 4 的 T4 补上）。
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
| 400 | 业务规则不满足 | `商品分类不存在`、`商品名称不能只包含空白`、`分类名称不能只包含空`、`会话标题不能只包含空白`、`至少提交一个需要修改的字段`、`字段 price 的值不允许为 null` | null |
| 404 | 资源不存在 | `商品不存在`（详情/删除）、`未找到商品`（改商品）、`分类不存在`、`会话不存在`、`Not Found`（未定义路径） | null |
| 409 | 冲突 / 存在依赖 | `分类名称已存在`、`分类下有其他商品，不能删除分类` | null |
| 422 | 参数校验失败 | `请求参数校验失败`（缺字段、类型错、价格超 2 位小数、`page<1`、`page_size>100`、路径 ID 非整数） | 明细数组 |
| 502 | 上游模型出错 | `模型服务鉴权失败，请检查 LLM_API_KEY`、`模型服务限流，请稍后重试`、`模型服务不可用`、`模型返回格式无法解析`、`模型返回内容为空`（见 4.6） | null |
| 504 | 上游超时 | `模型服务超时`（默认 30s，见 `LLM_TIMEOUT_SECONDS`） | null |
| 500 | 服务端错误 | `数据库操作失败，请检查记录后重试`、`服务器内部错误`；服务层包装：`查询商品列表失败，请稍后重试`、`统计商品数量失败，请稍后重试`、`查询商品失败，请稍后重试`、`查询分类失败，请稍后重试` | null |
| 503 | 依赖不可用 | 仅 `/readyz`：数据库连不上时返回裸 JSON `{"status":"unavailable","database":"down"}` | 裸 JSON |

### 1.4 字段类型与格式

| 字段 | 类型 | 格式 / 约束 |
| --- | --- | --- |
| `id` / `category_id` | int | 正整数；路径参数必须 > 0 |
| `name` | str | 1–50 字符；分类名全局唯一（重复 409），商品名不唯一 |
| `price` | **str** | 固定两位小数字符串，如 `"3.50"`；数据库 `DECIMAL(8,2)`，最多 8 位有效数字、2 位小数 |
| `stock` | int | ≥ 0 |
| `shelf_status` | bool | `true` 上架 / `false` 下架 |
| `create_time` | **str** | `YYYY-MM-DD HH:mm:ss`，**非 ISO 8601、无时区** |
| `category_name` | str | **只在分页 `items` 出现**；详情/新增/修改响应没有 |
| `product_count` | int | 只在 `/api/categories/statistics` |

### 1.5 路径与分页参数

- 路径 ID 非正整数 → 422（`loc: ["path", ...]`）；未定义路径 → 404 `Not Found`。
- 分页（`GET /api/products`）：`keyword` ≤50 字符（名称模糊匹配，`%`/`_` 按普通字符）、`category_id` >0、`page` ≥1 默认 1、`page_size` 1–100 默认 10；按 `id` 倒序。
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

## 2 商品接口（`/api/products`）

### 2.1 新增商品 `POST /api/products`

录入商品并返回完整商品；成功后 `data` 为商品对象（无 `category_name`）。

| 参数 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `category_id` | int | 是 | > 0，分类必须存在 |
| `name` | str | 是 | 1–50 字符，去首尾空白后不能为空 |
| `price` | number \| string | 是 | ≥ 0，最多 2 位小数、8 位有效数字 |
| `stock` | int | 否 | ≥ 0，默认 0 |
| `shelf_status` | bool | 否 | 默认 `true` |

错误：400 `商品分类不存在` / `商品名称不能只包含空白`；422 `请求参数校验失败`（缺字段、价格 3 位小数）。

```bash
curl -s -X POST http://127.0.0.1:8000/api/products -H "Content-Type: application/json" \
  -d '{"category_id":3,"name":"契约示例商品","price":"4.00","stock":5,"shelf_status":true}'
```

### 2.2 分页查询商品 `GET /api/products`

按名称关键词 + 分类筛选分页，按 `id` 倒序；`data` 为 `{items,total,page,page_size}`，`items` 每项比详情多 `category_name`；`total` 是**筛选后**总数。

| 参数 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `keyword` | str | 否 | ≤50 字符；名称模糊匹配；首尾空白被去掉，空串视为不筛选 |
| `category_id` | int | 否 | > 0；不传为全部 |
| `page` | int | 否 | ≥ 1，默认 1 |
| `page_size` | int | 否 | 1–100，默认 10 |

错误：422 `请求参数校验失败`（`page=0`、`page_size=101`、`keyword` 超 50 字符）。

```json
{"code":200,"message":"请求成功","data":{"items":[{"id":20,"category_id":3,"name":"东方树叶","price":"5.50","stock":35,"shelf_status":true,"create_time":"2026-11-06 00:10:36","category_name":"饮料"},{"id":16,"category_id":8,"name":"特仑苏","price":"6.80","stock":30,"shelf_status":true,"create_time":"2026-11-06 00:01:22","category_name":"乳品"}],"total":14,"page":1,"page_size":2}}
```

### 2.3 统计商品总数 `GET /api/products/count`

无参数；`data` 为 `{total}`，统计**全部商品**，不应用列表的筛选条件。错误：500 见 1.3。

```json
{"code":200,"message":"请求成功","data":{"total":14}}
```

### 2.4 商品详情 `GET /api/products/{product_id}`

按 ID 查单个商品；`data` 为商品对象（**无 `category_name`**，编辑回填分类用 `category_id`）。

| 参数 | 位置 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- | --- |
| `product_id` | path | int | 是 | > 0 |

错误：404 `商品不存在`；422 `请求参数校验失败`（ID 非整数/0/负数）。

```json
{"code":200,"message":"请求成功","data":{"id":16,"category_id":8,"name":"特仑苏","price":"6.80","stock":30,"shelf_status":true,"create_time":"2026-11-06 00:01:22"}}
```

### 2.5 修改商品 `PATCH /api/products/{product_id}`

局部更新，只写提交的字段；字段全可选但**至少提交一个**；显式传 `null` 返回 400。成功 `data` 为修改后商品（无 `category_name`）。

| 参数 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `category_id` | int | 否 | > 0，分类必须存在 |
| `name` | str | 否 | 1–50 字符；去首尾空白后不能为空（纯空白 400） |
| `price` | number \| string | 否 | ≥ 0，最多 2 位小数 |
| `stock` | int | 否 | ≥ 0 |
| `shelf_status` | bool | 否 | — |

错误：400 `至少提交一个需要修改的字段` / `字段 price 的值不允许为 null` / `商品分类不存在`；404 `未找到商品`；422 校验失败。

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/products/51 -H "Content-Type: application/json" \
  -d '{"price":"4.50","shelf_status":false}'
```

### 2.6 删除商品 `DELETE /api/products/{product_id}`

按 ID 删除；成功 `data` 为 `null`。路径参数同上（>0）。错误：404 `商品不存在`（含重复删除）；422 校验失败。

```bash
curl -s -X DELETE http://127.0.0.1:8000/api/products/51
```

## 3 分类接口（`/api/categories`）

### 3.1 新增分类 `POST /api/categories`

创建分类并返回分类对象（`id`/`name`/`create_time`）；名称全局唯一。

| 参数 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `name` | str | 是 | 1–50 字符；去首尾空白后不能为空 |

错误：409 `分类名称已存在`；400 `分类名称不能只包含空`；422 `请求参数校验失败`（缺 `name`）。

```bash
curl -s -X POST http://127.0.0.1:8000/api/categories -H "Content-Type: application/json" \
  -d '{"name":"契约示例分类"}'
```

### 3.2 分类列表 `GET /api/categories`

无参数；`data` 为分类对象数组，按 `id` **倒序**；无分类时 `data: []`。错误：500 见 1.3。

```json
{"code":200,"message":"请求成功","data":[{"id":8,"name":"乳品","create_time":"2026-11-06 00:01:22"},{"id":7,"name":"零食","create_time":"2026-11-06 00:01:22"},{"id":3,"name":"饮料","create_time":"2026-11-03 16:58:42"}]}
```

### 3.3 修改分类名称 `PATCH /api/categories/{category_id}`

改名并返回分类对象。

| 参数 | 位置 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- | --- |
| `category_id` | path | int | 是 | > 0 |
| `name` | body | str | 是 | 1–50 字符；去首尾空白后不能为空；全局唯一 |

错误：404 `分类不存在`；409 `分类名称已存在`；400 `分类名称不能只包含空`；422 `请求参数校验失败`。
与 POST 同一套规则：先 `strip()` 再判空，**只传空格会 400，不会存进库**；资源不存在时优先 404。

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/categories/26 -H "Content-Type: application/json" \
  -d '{"name":"契约示例分类-改名"}'
```

### 3.4 删除分类 `DELETE /api/categories/{category_id}`

仅允许删除没有商品的分类；成功 `data` 为 `null`。路径参数 >0。错误：404 `分类不存在`；409 `分类下有其他商品，不能删除分类`。

```bash
curl -s -X DELETE http://127.0.0.1:8000/api/categories/26
```

### 3.5 分类商品数统计 `GET /api/categories/statistics`

无参数；`data` 为 `[{id,name,product_count}]`，按 `id` **升序**；没有商品的分类也返回，`product_count` 为 0。错误：500 见 1.3。

```json
{"code":200,"message":"请求成功","data":[{"id":3,"name":"饮料","product_count":6},{"id":7,"name":"零食","product_count":4},{"id":8,"name":"乳品","product_count":4}]}
```

> 分类商品数只有本接口提供；`GET /api/categories` 不含 `product_count`，前端需按 `id` 合并两份数据。

## 4 对话接口（`/api/conversations`）

阶段 4 新增：会话与消息都落库，刷新后仍在；首版同步返回模型回复（流式见 T4b）。
本节会话 CRUD，4.6 是发消息（同步调用模型）。

### 4.1 新建会话 `POST /api/conversations`

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

### 4.2 会话列表 `GET /api/conversations`

查询参数：`page`（默认 1，≥1）、`page_size`（默认 10，1–100）。
排序：`update_time` 倒序，同秒内按 `id` 倒序（新建的会话一定在最前）。

`data` 是分页结构，多一个 `message_count`（该会话消息条数，用一次聚合查询算出，不产生 N+1）：

```json
{"items":[{"id":2,"title":"新会话","agent_key":"default","update_time":"2026-11-07 23:25:40","create_time":"2026-11-07 23:25:40","message_count":0}],"total":1,"page":1,"page_size":10}
```

### 4.3 会话详情 `GET /api/conversations/{id}`

`data` 在会话字段外多一个 `messages`，按发送顺序（`id` 升序）排列；用户消息的 `model` 为 `null`。

```json
{"id":1,"title":"改名后","agent_key":"default","update_time":"2026-11-07 23:25:40","create_time":"2026-11-07 23:25:40","messages":[{"id":1,"conversation_id":1,"role":"user","content":"你好","model":null,"create_time":"2026-11-07 23:25:41"}]}
```

空会话返回 `"messages": []`；不存在返回 404 `会话不存在`。

### 4.4 重命名会话 `PATCH /api/conversations/{id}`

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `title` | string | 是 | 1–100；去首尾空白后不能为空 |

- `""` → 422（schema 的 `min_length=1`）
- `"   "` → 400 `会话标题不能只包含空白`（service 层判断）
- id 不存在时**优先**返回 404，不再看标题是否合法

### 4.5 删除会话 `DELETE /api/conversations/{id}`

删除会话及其全部消息（数据库外键 `ON DELETE CASCADE` + ORM `cascade="all, delete-orphan"`）。成功返回 `data: null`；不存在返回 404。

### 4.6 发送消息 `POST /api/conversations/{id}/messages`

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

模型由 `LLM_PROVIDER` 决定（默认 `fake`，回显形如 `[fake] 收到：<你的话>`）。上游故障映射见下表：

| 场景 | HTTP/code | 文案 |
| --- | --- | --- |
| 鉴权失败（401/403） | 502 | `模型服务鉴权失败，请检查 LLM_API_KEY` |
| 限流（429） | 502 | `模型服务限流，请稍后重试` |
| 其他上游 4xx/5xx | 502 | `模型服务不可用` |
| 返回体不是预期 JSON / 无 content | 502 | `模型返回格式无法解析` / `模型返回内容为空` |
| 超时（默认 30s） | 504 | `模型服务超时` |

上游的原始报错不会透传给前端，只进服务端日志。

## 5 前端接入注意事项

1. **统一解包**：所有业务响应都是 `{code,message,data}`；axios 拦截器里 `code !== 200` 时抛错并展示 `message`，业务层只拿 `data`。
2. **422 的 `data` 是数组**：不是 `null`，也不是字符串；表单页可读 `data[0].loc` 定位字段，列表页只 toast `message` 即可。
3. **`price` 是字符串**：如 `"4.50"`；展示直接拼 `¥`，需要计算时 `Number(price)`。
4. **`create_time` 非 ISO**：形如 `"2026-11-06 00:01:22"`；`new Date(...)` 在 Safari 会 Invalid Date，需先 `s.replace(" ", "T")`。
5. **`category_name` 只在分页 `items`**：详情/新增/修改都没有；编辑回填分类请用 `category_id` 匹配下拉。
6. **分类商品数要合并 statistics**：`GET /api/categories` 只有 `id/name/create_time`；与 `GET /api/categories/statistics` 按 `id` 合并（统计升序、列表倒序，不要假设同序）。
7. **两种 total 不要混用**：分页 `total` 是筛选后总数（分页器用）；`/api/products/count` 是全量（概览用）。
8. **分页交互**：`page` 默认 1、`page_size` 默认 10（上限 100）；搜索/筛选变化时 `page` 重置为 1；删除当前页最后一条且 `page>1` 时回上一页。
9. **列表按 `id` 倒序**：新增成功后回第 1 页即可看到新商品。
10. **成功也是 HTTP 200**：不要只按 201 判成功；删除成功无数据（`data: null`）。
11. **404 文案有差异**：详情/删除是 `商品不存在`，修改是 `未找到商品`；直接展示后端 `message`，不要前端硬编码。
12. **409 分类相关**：重名或删除有商品的分类都会 409；前端用 `ElMessage` 提示，并引导「先处理分类下的商品」。
13. **名称统一去首尾空白**：商品与分类、新增与改名都先 `strip()` 再判空——纯空白 → 400，空串 → 422。前端仍建议 `trim()` 后再提交，省一次往返。
14. **CORS / 代理**：开发期推荐 Vite proxy（`/api` → `http://127.0.0.1:8000`）；直连时后端已放行 5173/4173（见 1.6）。

## 6 启动、测试与工具链（不在此展开）

- 后端依赖安装、建库、迁移、启动、seed、测试命令：`python/fastapi-demo/README.md`（「快速开始」「常用命令」）。
- 本地自检、pre-commit、CI 三条链路与各工具职责：`docs/toolchain.md`。
- 本文件变更历史：`git log -- docs/api.md`。

## 附录 A：数据模型

`categories`（分类表）

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | int | 主键，自增 | 分类 ID |
| `name` | varchar(50) | NOT NULL，**UNIQUE** | 分类名称 |
| `create_time` | datetime | NOT NULL，默认当前时间 | 创建时间 |

`products`（商品表）

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | int | 主键，自增 | 商品 ID |
| `category_id` | int | NOT NULL，外键 → `categories.id` | 所属分类 |
| `name` | varchar(50) | NOT NULL | 商品名称（不唯一） |
| `price` | decimal(8,2) | NOT NULL | 单价（元） |
| `stock` | int | NOT NULL，默认 0 | 库存 |
| `shelf_status` | bool | NOT NULL，默认 1 | 是否上架 |
| `create_time` | datetime | NOT NULL，默认当前时间 | 创建时间 |

`conversations`（对话会话表，阶段 4 新增）

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | int | 主键，自增 | 会话 ID |
| `title` | varchar(100) | NOT NULL，默认 `新会话` | 会话标题 |
| `agent_key` | varchar(50) | NOT NULL，默认 `default` | 所属代理标识（为多 Agent 预留） |
| `update_time` | datetime | NOT NULL，默认当前时间，ON UPDATE | 最后活动时间（列表排序用，建索引） |
| `create_time` | datetime | NOT NULL，默认当前时间 | 创建时间 |

`messages`（消息表）

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | int | 主键，自增 | 消息 ID |
| `conversation_id` | int | NOT NULL，外键 → `conversations.id`，ON DELETE CASCADE | 所属会话（建索引） |
| `role` | varchar(16) | NOT NULL | `user` / `assistant` / `system` |
| `content` | text | NOT NULL | 消息正文 |
| `model` | varchar(64) | 可空 | 生成该回复的模型；用户消息为空 |
| `create_time` | datetime | NOT NULL，默认当前时间 | 创建时间 |

## 附录 B：演示数据（`python -m app.seed`）

- 幂等：按名称判断，已存在的分类/商品直接跳过（不修改、不重复插入），可反复执行；结束打印「新增分类/商品、跳过、库内总量」。
- 3 个分类：饮料、零食、乳品；12 个商品，每个分类 4 个，其中 2 个下架（奥利奥饼干、光明酸奶），用于演示分页与状态标签。
- 商品：饮料=可口可乐/雪碧/农夫山泉/东方树叶；零食=乐事薯片/奥利奥饼干/旺旺雪饼/三只松鼠坚果；乳品=蒙牛纯牛奶/光明酸奶/伊利安慕希/特仑苏。
- 运行：`cd python/fastapi-demo && uv run python -m app.seed`；在已有同名数据时按名称跳过（例如库里已有「雪碧」则只新增其余 11 条）。
