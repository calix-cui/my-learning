# 商品管理网站 · 后端 API 契约

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.0 |
| 日期 | 2026-11-06 |
| 作者 | Python 后端（python-backend-dev） |
| 状态 | 已实现，`make check` 全绿；本文所有示例均为真实调用返回 |
| 对应后端 | `python/fastapi-demo/`（FastAPI 0.124.4 + SQLAlchemy 2.0.44 + MySQL 8.0） |
| 在线调试 | 启动后端后访问 `http://127.0.0.1:8000/docs`（Swagger UI）或 `http://127.0.0.1:8000/redoc` |

> **示例采集说明**：本文示例是起服务后用 curl 实际调用、原样复制返回结果得到的。
> 采集时后端运行在 **8020** 端口（8000 供 Leader 联调），除端口外与 8000 的行为完全一致；
> 示例中的时间、ID 为采集当次数据，你自己调用时数值会不同，但字段与格式不变。

---

## 1. 通用约定

### 1.1 基础地址与路由前缀

| 项 | 值 |
| --- | --- |
| 开发环境 baseURL | `http://127.0.0.1:8000` |
| 业务接口统一前缀 | `/api` |
| 商品接口前缀 | `/api/products` |
| 分类接口前缀 | `/api/categories` |
| 请求/响应编码 | `UTF-8`，请求体为 `application/json` |

前端开发期建议通过 Vite proxy 把 `/api` 转发到 `http://127.0.0.1:8000`，axios 的 `baseURL` 写 `/api`，
这样既不依赖 CORS，也不用改环境地址；后端已同时配置了 CORS（见 1.6），直连也能跑通。

### 1.2 统一响应结构

**所有**接口（包括错误）都返回同一种 JSON 外壳，不会直接返回裸数组或裸对象：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | int | 业务状态码，**与 HTTP 状态码保持一致**（成功 200，失败为对应 4xx/5xx） |
| `message` | str | 中文提示语，成功固定为 `请求成功`；失败时可直接展示给用户 |
| `data` | any | 业务数据。成功时按接口而定；失败时为 `null`（422 校验失败时为错误明细数组）；无返回值的删除操作为 `null` |

成功示例（`GET /api/products/13`）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "id": 13,
    "category_id": 8,
    "name": "蒙牛纯牛奶",
    "price": "4.50",
    "stock": 90,
    "shelf_status": true,
    "create_time": "2026-11-06 00:01:22"
  }
}
```

失败示例（`POST /api/products`，分类不存在）：

```json
{
  "code": 400,
  "message": "商品分类不存在",
  "data": null
}
```

> 注意：**成功也返回 HTTP 200 + `code: 200`**，新增接口同样是 200，不是 201。
> 前端判断成功请用 `res.data.code === 200`（axios 拦截器里已做），失败时 HTTP 状态码与 `code` 相同。

### 1.3 错误码表

错误码来自 `app/common/exceptions.py` 与各 service 抛出的 `BusinessError`，语义如下：

| HTTP / code | 含义 | 触发场景（真实例子） | `data` |
| --- | --- | --- | --- |
| 200 | 成功 | 所有正常请求 | 业务数据或 `null` |
| 400 | 业务规则不满足 | 名称只包含空白、分类不存在、PATCH 提交空对象、显式传 `null` 清空字段 | `null` |
| 404 | 资源不存在 | 商品/分类 ID 不存在；访问了未定义的路径（如 `/api/unknown`） | `null` |
| 409 | 冲突 / 存在依赖 | 分类名称重复；删除仍有商品的分类 | `null` |
| 422 | 请求参数校验失败 | 缺必填字段、类型错误、价格超过 2 位小数、`page<1`、`page_size>100`、路径 ID 非整数 | **错误明细数组** |
| 500 | 服务端异常 | 数据库连接/执行失败、未预期异常（统一文案，不暴露堆栈） | `null` |

422 的 `data` 是 pydantic 错误明细数组，前端一般只需展示 `message`，调试时可看 `loc` 定位字段：

```json
{
  "code": 422,
  "message": "请求参数校验失败",
  "data": [
    {
      "type": "decimal_max_places",
      "loc": ["body", "price"],
      "msg": "Decimal input should have no more than 2 decimal places",
      "input": "3.999",
      "ctx": { "decimal_places": 2 }
    }
  ]
}
```

### 1.4 字段类型与格式约定

| 字段 | 返回类型 | 格式 / 约束 | 备注 |
| --- | --- | --- | --- |
| `id` | int | 正整数（路径参数要求 `> 0`） | 数据库自增，删除后不复用 |
| `name` | str | 1–50 字符，首尾空白由 service 去除；全空白 → 400 | 分类名全局唯一；商品名不要求唯一（seed 按名称判重） |
| `price` | **str** | 固定两位小数的字符串，如 `"3.50"`、`"28.80"` | 数据库为 `DECIMAL(8,2)`；不超过 8 位有效数字、最多 2 位小数 |
| `stock` | int | `>= 0` | 可为 0（配合下架表示无货） |
| `shelf_status` | bool | `true` 上架 / `false` 下架 | 请求体里也接受 `true/false` |
| `create_time` | **str** | `YYYY-MM-DD HH:mm:ss`，**不是 ISO 8601，无时区** | 例：`"2026-11-06 00:01:22"` |
| `category_id` | int | 正整数，且必须真实存在 | 不存在时创建/修改返回 400 |
| `category_name` | str | 分类名称 | **只在分页接口的 `items` 里出现**，详情/新增/修改响应没有该字段 |
| `product_count` | int | `>= 0` | 只出现在 `/api/categories/statistics` |

### 1.5 路径与参数通用规则

- 所有路径 ID 都是**正整数**：`0`、负数、`abc` → 422（`loc: ["path", ...]`）。
- 查询参数非法（如 `page=0`、`page_size=101`）→ 422。
- 访问未定义路径 → 404 + `{"code":404,"message":"Not Found","data":null}`。
- 请求体不是合法 JSON 或字段类型不对 → 422。

### 1.6 CORS（跨域）

`app/main.py` 通过 `CORSMiddleware` 放行以下 4 个前端来源（Vite dev 5173 与 Vite preview 4173，各含 localhost 与 127.0.0.1 两种写法）：

```text
http://localhost:5173
http://127.0.0.1:5173
http://localhost:4173
http://127.0.0.1:4173
```

配置为 `allow_methods=["*"]`、`allow_headers=["*"]`、`allow_credentials=False`。
实际返回（对 `Origin: http://localhost:5173` 的预检请求）：

```http
HTTP/1.1 200 OK
vary: Origin
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-max-age: 600
access-control-allow-origin: http://localhost:5173
access-control-allow-headers: content-type
```

- 预检（`OPTIONS`）由中间件直接回 200，不会进业务路由，因此后端不需要额外写 OPTIONS 接口。
- 不在白名单的 `Origin` 不会拿到 `access-control-allow-origin` 响应头，浏览器会拦截。
- 前端若走 Vite proxy（`/api` → `127.0.0.1:8000`），浏览器看到的是同源请求，CORS 不参与。
- 生产部署时需把白名单收窄为真实域名（`ALLOWED_ORIGINS` 在 `app/main.py` 顶部）。

---

## 2. 接口总览

共 **11** 个业务接口，全部返回 1.2 的统一外壳。

| # | 方法 | 路径 | 用途 | 成功 `data` |
| --- | --- | --- | --- | --- |
| 1 | POST | `/api/products` | 新增商品 | 商品对象（无 `category_name`） |
| 2 | GET | `/api/products` | 分页 + 关键词/分类筛选 | `{items, total, page, page_size}` |
| 3 | GET | `/api/products/count` | 统计全部商品数 | `{total}` |
| 4 | GET | `/api/products/{product_id}` | 商品详情 | 商品对象（无 `category_name`） |
| 5 | PATCH | `/api/products/{product_id}` | 局部修改商品 | 修改后的商品对象 |
| 6 | DELETE | `/api/products/{product_id}` | 删除商品 | `null` |
| 7 | POST | `/api/categories` | 新增分类 | 分类对象 |
| 8 | GET | `/api/categories` | 分类列表 | 分类对象数组 |
| 9 | PATCH | `/api/categories/{category_id}` | 分类改名 | 修改后的分类对象 |
| 10 | DELETE | `/api/categories/{category_id}` | 删除分类（无商品时） | `null` |
| 11 | GET | `/api/categories/statistics` | 各分类商品数 | `[{id, name, product_count}]` |

> 路由顺序注意：`/api/products/count` 与 `/api/categories/statistics` 是固定路径，必须先于 `{id}` 匹配，
> 后端已按正确顺序注册，前端直接按上表路径调用即可。

---

## 3. 商品接口

### 3.1 新增商品 `POST /api/products`

| 项 | 内容 |
| --- | --- |
| 用途 | 录入一个商品，返回带自增 ID 与创建时间的完整商品 |
| 请求体 | `application/json` |
| 前置校验 | `category_id` 指向的分类必须存在，否则 400 |

**请求参数（body）**

| 参数 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `category_id` | int | 是 | `> 0`，分类须存在 | 所属分类 |
| `name` | str | 是 | 1–50 字符；去除首尾空白后不能为空 | 商品名称 |
| `price` | number \| string | 是 | `>= 0`，最多 2 位小数，最多 8 位有效数字 | 单价（元），传 `4`、`"4.00"`、`4.5` 均可 |
| `stock` | int | 否 | `>= 0`，默认 `0` | 库存 |
| `shelf_status` | bool | 否 | 默认 `true` | 是否上架 |

**成功响应**（HTTP 200）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "id": 18,
    "category_id": 3,
    "name": "康师傅冰红茶",
    "price": "4.00",
    "stock": 50,
    "shelf_status": true,
    "create_time": "2026-11-06 00:02:03"
  }
}
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| 分类不存在 | 400 | `商品分类不存在` |
| 名称只包含空白 | 400 | `商品名称不能只包含空白` |
| 价格 3 位小数 | 422 | `请求参数校验失败` |
| 缺少 `name` / `category_id` | 422 | `请求参数校验失败` |

```json
{ "code": 400, "message": "商品分类不存在", "data": null }
```

**curl**

```bash
curl -s -X POST http://127.0.0.1:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{"category_id":3,"name":"康师傅冰红茶","price":"4.00","stock":50,"shelf_status":true}'
```

---

### 3.2 分页查询商品 `GET /api/products`

| 项 | 内容 |
| --- | --- |
| 用途 | 商品列表页：支持名称关键词 + 分类筛选 + 分页，按商品 ID **倒序**（新录入的排最前） |
| 请求参数位置 | query string |

**请求参数（query）**

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `keyword` | str | 否 | 无（不筛选） | 最长 50 字符 | 商品名称模糊匹配，`%`、`_` 按普通字符处理；首尾空白会被去掉 |
| `category_id` | int | 否 | 无（全部） | `> 0` | 按分类筛选；不传表示全部 |
| `page` | int | 否 | `1` | `>= 1` | 页码 |
| `page_size` | int | 否 | `10` | `1–100` | 每页条数 |

**成功响应**（HTTP 200，`page=1&page_size=5`，共 14 条）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "items": [
      {
        "id": 16,
        "category_id": 8,
        "name": "特仑苏",
        "price": "6.80",
        "stock": 30,
        "shelf_status": true,
        "create_time": "2026-11-06 00:01:22",
        "category_name": "乳品"
      },
      {
        "id": 15,
        "category_id": 8,
        "name": "伊利安慕希",
        "price": "7.50",
        "stock": 66,
        "shelf_status": true,
        "create_time": "2026-11-06 00:01:22",
        "category_name": "乳品"
      },
      {
        "id": 14,
        "category_id": 8,
        "name": "光明酸奶",
        "price": "3.80",
        "stock": 0,
        "shelf_status": false,
        "create_time": "2026-11-06 00:01:22",
        "category_name": "乳品"
      },
      {
        "id": 13,
        "category_id": 8,
        "name": "蒙牛纯牛奶",
        "price": "4.50",
        "stock": 90,
        "shelf_status": true,
        "create_time": "2026-11-06 00:01:22",
        "category_name": "乳品"
      },
      {
        "id": 12,
        "category_id": 7,
        "name": "三只松鼠坚果",
        "price": "28.80",
        "stock": 12,
        "shelf_status": true,
        "create_time": "2026-11-06 00:01:22",
        "category_name": "零食"
      }
    ],
    "total": 14,
    "page": 1,
    "page_size": 5
  }
}
```

**响应字段**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `items` | array | 当前页商品；每项比详情接口**多一个 `category_name`** |
| `total` | int | 应用 `keyword`/`category_id` 筛选后的总条数（用于分页器） |
| `page` | int | 回显当前页码（= 请求的 `page`） |
| `page_size` | int | 回显每页条数（= 请求的 `page_size`） |

**筛选示例**（`keyword=牛奶`，命中 1 条）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "items": [
      {
        "id": 13,
        "category_id": 8,
        "name": "蒙牛纯牛奶",
        "price": "4.50",
        "stock": 90,
        "shelf_status": true,
        "create_time": "2026-11-06 00:01:22",
        "category_name": "乳品"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| `page=0` | 422 | `请求参数校验失败` |
| `page_size=101` | 422 | `请求参数校验失败` |
| `category_id=0` | 422 | `请求参数校验失败` |
| `keyword` 超过 50 字符 | 422 | `请求参数校验失败` |

```json
{
  "code": 422,
  "message": "请求参数校验失败",
  "data": [
    {
      "type": "greater_than_equal",
      "loc": ["query", "page"],
      "msg": "Input should be greater than or equal to 1",
      "input": "0",
      "ctx": { "ge": 1 }
    }
  ]
}
```

**curl**

```bash
# 第 1 页，每页 5 条
curl -s "http://127.0.0.1:8000/api/products?page=1&page_size=5"

# 关键词搜索（中文需 urlencode，curl 可用 --data-urlencode）
curl -s -G "http://127.0.0.1:8000/api/products" \
  --data-urlencode "keyword=牛奶" --data-urlencode "page=1" --data-urlencode "page_size=10"

# 按分类筛选（零食 category_id=7）
curl -s "http://127.0.0.1:8000/api/products?category_id=7&page=1&page_size=10"
```

---

### 3.3 统计商品总数 `GET /api/products/count`

| 项 | 内容 |
| --- | --- |
| 用途 | 概览/列表顶部「商品总数」 |
| 请求参数 | 无 |
| 注意 | 统计**全部商品**，不应用列表页的 `keyword`/`category_id` 筛选 |

**成功响应**（HTTP 200）：

```json
{ "code": 200, "message": "请求成功", "data": { "total": 14 } }
```

**curl**

```bash
curl -s http://127.0.0.1:8000/api/products/count
```

---

### 3.4 商品详情 `GET /api/products/{product_id}`

| 项 | 内容 |
| --- | --- |
| 用途 | 按 ID 查单个商品（编辑回填、详情弹窗） |
| 注意 | 返回**不含 `category_name`**，编辑回填分类请用 `category_id` |

**请求参数（path）**

| 参数 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `product_id` | int | 是 | `> 0` | 商品 ID |

**成功响应**（HTTP 200）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "id": 13,
    "category_id": 8,
    "name": "蒙牛纯牛奶",
    "price": "4.50",
    "stock": 90,
    "shelf_status": true,
    "create_time": "2026-11-06 00:01:22"
  }
}
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| ID 不存在 | 404 | `商品不存在` |
| ID 非整数 / 0 / 负数 | 422 | `请求参数校验失败` |

```json
{ "code": 404, "message": "商品不存在", "data": null }
```

**curl**

```bash
curl -s http://127.0.0.1:8000/api/products/13
```

---

### 3.5 修改商品 `PATCH /api/products/{product_id}`

| 项 | 内容 |
| --- | --- |
| 用途 | 编辑弹窗保存；**局部更新**，只写提交的字段 |
| 请求体 | `application/json`，字段全部可选，但**至少提交一个** |
| 注意 | 显式传 `null` 会返回 400（本项目的业务字段都不允许清空） |

**请求参数（path + body）**

| 参数 | 位置 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `product_id` | path | int | 是 | `> 0` | 商品 ID |
| `category_id` | body | int | 否 | `> 0`，分类须存在 | 改分类 |
| `name` | body | str | 否 | 1–50 字符，去空白后非空 | 改名称 |
| `price` | body | number \| string | 否 | `>= 0`，最多 2 位小数 | 改价格 |
| `stock` | body | int | 否 | `>= 0` | 改库存 |
| `shelf_status` | body | bool | 否 | — | 上架 / 下架 |

**成功响应**（HTTP 200，改价格、库存、状态）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "id": 18,
    "category_id": 3,
    "name": "康师傅冰红茶",
    "price": "4.50",
    "stock": 45,
    "shelf_status": false,
    "create_time": "2026-11-06 00:02:03"
  }
}
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| 空对象 `{}`（没有要改的字段） | 400 | `至少提交一个需要修改的字段` |
| 显式提交 `null` | 400 | `字段 price 的值不允许为 null`（字段名随提交变化） |
| 商品不存在 | 404 | `未找到商品` |
| 分类不存在 | 400 | `商品分类不存在` |
| 价格 3 位小数 | 422 | `请求参数校验失败` |

```json
{ "code": 400, "message": "至少提交一个需要修改的字段", "data": null }
```

> 删除与修改的 404 文案不同：详情/删除是 `商品不存在`，修改是 `未找到商品`。
> 前端直接展示后端 `message` 即可，不要在前端硬编码文案。

**curl**

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/products/18 \
  -H "Content-Type: application/json" \
  -d '{"price":"4.50","stock":45,"shelf_status":false}'
```

---

### 3.6 删除商品 `DELETE /api/products/{product_id}`

| 项 | 内容 |
| --- | --- |
| 用途 | 列表行内「删除」，二次确认后调用 |
| 请求参数 | path `product_id`，`> 0` |
| 成功响应 | `data` 为 `null` |

**成功响应**（HTTP 200）：

```json
{ "code": 200, "message": "请求成功", "data": null }
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| 商品不存在（含重复删除） | 404 | `商品不存在` |
| ID 非整数 / 0 / 负数 | 422 | `请求参数校验失败` |

```json
{ "code": 404, "message": "商品不存在", "data": null }
```

**curl**

```bash
curl -s -X DELETE http://127.0.0.1:8000/api/products/18
```

---

## 4. 分类接口

### 4.1 新增分类 `POST /api/categories`

| 项 | 内容 |
| --- | --- |
| 用途 | 分类管理页「新增分类」 |
| 请求体 | `application/json` |
| 唯一性 | 分类名称全局唯一，重名返回 409 |

**请求参数（body）**

| 参数 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | str | 是 | 1–50 字符；去除首尾空白后不能为空 | 分类名称 |

**成功响应**（HTTP 200）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": { "id": 11, "name": "茶叶", "create_time": "2026-11-06 00:02:03" }
}
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| 名称重复 | 409 | `分类名称已存在` |
| 名称只包含空白 | 400 | `分类名称不能只包含空` |
| 缺少 `name` | 422 | `请求参数校验失败` |

```json
{ "code": 409, "message": "分类名称已存在", "data": null }
```

**curl**

```bash
curl -s -X POST http://127.0.0.1:8000/api/categories \
  -H "Content-Type: application/json" \
  -d '{"name":"茶叶"}'
```

---

### 4.2 分类列表 `GET /api/categories`

| 项 | 内容 |
| --- | --- |
| 用途 | 分类管理表格、商品表单里的分类下拉、概览里的分类数 |
| 请求参数 | 无 |
| 排序 | 按分类 ID **倒序**（新建的排在前面） |
| 空数据 | 返回 `data: []`，不是 null |

**成功响应**（HTTP 200）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": [
    { "id": 8, "name": "乳品", "create_time": "2026-11-06 00:01:22" },
    { "id": 7, "name": "零食", "create_time": "2026-11-06 00:01:22" },
    { "id": 3, "name": "饮料", "create_time": "2026-11-03 16:58:42" }
  ]
}
```

**curl**

```bash
curl -s http://127.0.0.1:8000/api/categories
```

> 列表接口不返回 `product_count`；分类管理表格的「商品数」列请用 4.5 的统计接口。

---

### 4.3 修改分类名称 `PATCH /api/categories/{category_id}`

| 项 | 内容 |
| --- | --- |
| 用途 | 分类管理页「改名」 |
| 请求体 | `application/json` |
| 注意 | 重名 409；修改不存在的分类 404 |

**请求参数（path + body）**

| 参数 | 位置 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `category_id` | path | int | 是 | `> 0` | 分类 ID |
| `name` | body | str | 是 | 1–50 字符，去空白后非空，全局唯一 | 新名称 |

**成功响应**（HTTP 200）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": { "id": 11, "name": "茶叶-改名", "create_time": "2026-11-06 00:02:03" }
}
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| 分类不存在 | 404 | `分类不存在` |
| 新名称与其它分类重复 | 409 | `分类名称已存在` |
| 名称为空 / 全空白 | 400 / 422 | `分类名称不能只包含空` / `请求参数校验失败` |

```json
{ "code": 409, "message": "分类名称已存在", "data": null }
```

**curl**

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/categories/11 \
  -H "Content-Type: application/json" \
  -d '{"name":"茶叶-改名"}'
```

---

### 4.4 删除分类 `DELETE /api/categories/{category_id}`

| 项 | 内容 |
| --- | --- |
| 用途 | 分类管理页「删除」，二次确认后调用 |
| 约束 | **分类下还有商品时拒绝删除**（409），前端要提示并提供「先移走/删除商品」的指引 |
| 成功响应 | `data` 为 `null` |

**成功响应**（HTTP 200）：

```json
{ "code": 200, "message": "请求成功", "data": null }
```

**典型错误**

| 场景 | HTTP | message |
| --- | --- | --- |
| 分类下仍有商品 | 409 | `分类下有其他商品，不能删除分类` |
| 分类不存在（含重复删除） | 404 | `分类不存在` |

```json
{ "code": 409, "message": "分类下有其他商品，不能删除分类", "data": null }
```

**curl**

```bash
# 删除空分类（成功）
curl -s -X DELETE http://127.0.0.1:8000/api/categories/11

# 删除仍有商品的分类（409）
curl -s -X DELETE http://127.0.0.1:8000/api/categories/7
```

---

### 4.5 分类商品数统计 `GET /api/categories/statistics`

| 项 | 内容 |
| --- | --- |
| 用途 | 概览页「各分类商品数」、分类管理表格「商品数」列 |
| 请求参数 | 无 |
| 排序 | 按分类 ID **升序**（与 4.2 列表的倒序相反，前端不要混用） |
| 空数据 | 返回 `data: []` |

**成功响应**（HTTP 200）：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": [
    { "id": 3, "name": "饮料", "product_count": 6 },
    { "id": 7, "name": "零食", "product_count": 4 },
    { "id": 8, "name": "乳品", "product_count": 4 }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 分类 ID |
| `name` | str | 分类名称 |
| `product_count` | int | 该分类下商品数量；没有商品的分类也会返回，值为 0 |

**curl**

```bash
curl -s http://127.0.0.1:8000/api/categories/statistics
```

---

## 5. 前端接入注意事项（重要）

1. **统一解包**：所有接口外层都是 `{code, message, data}`。axios 响应拦截器里判断 `code !== 200` 时
   `throw new Error(message)`；业务层只拿 `data`。
2. **成功=HTTP 200**：新增也是 200 而不是 201，不要只按 `201` 判成功。
3. **`price` 是字符串**：返回 `"4.50"`、`"28.80"`，不是 number。展示用 `¥ ${price}`（后端已保证两位小数），
   需要数值计算时用 `Number(price)`；提交给后端时传字符串或数字都可以。
4. **`create_time` 不是 ISO 8601**：格式为 `"2026-11-06 00:01:22"`，没有 `T` 也没有时区。
   直接 `new Date("2026-11-06 00:01:22")` 在部分浏览器（如 Safari）会得到 Invalid Date，
   需先替换空格：`new Date(s.replace(" ", "T"))`，或按字符串直接展示。
5. **`category_name` 只出现在分页 `items`**：`GET /api/products/{id}`、新增、修改的响应都**没有**
   `category_name`。编辑回填分类请用 `category_id` 匹配分类下拉；表格展示用列表项里的 `category_name`。
6. **分页参数默认值**：`page=1`、`page_size=10`，`page_size` 上限 100。搜索/筛选变化时把 `page` 重置为 1；
   删除某页最后一条后如果 `page > 1` 且该页为空，前端自动回上一页重新请求。
7. **列表排序是 `id` 倒序**：刚新增的商品出现在第 1 页最前，所以新增成功后回到第 1 页能看到它。
8. **筛选 `total` 语义**：分页接口的 `total` 是**筛选后**的总数（分页器用）；
   `/api/products/count` 的 `total` 是**全部商品**数（概览用），两者不同，不要混用。
9. **筛选参数**：`keyword` 只匹配商品名称（不搜分类）；`category_id` 传 `null`/空字符串效果等同于不传
   （axios 记得过滤空值，否则 `category_id=` 会 422）；`keyword` 最长 50 字符。
10. **错误处理**：直接展示后端 `message`（中文、可直接给用户看）。后端 404 文案有差异
    （`商品不存在` vs `未找到商品`），不要前端硬编码。422 的 `data` 是错误明细数组，列表页一般只 toast `message`；
    表单页可读 `data[0].loc` 定位到具体字段。
11. **409 分类相关**：新增重名 → `分类名称已存在`；删除有商品分类 → `分类下有其他商品，不能删除分类`。
    前端在分类管理页收到 409 时用 `ElMessage` 展示，不要静默。
12. **删除分类后**：如果该分类正在商品列表的筛选条件里，前端要清除筛选并重新拉列表，避免出现「空列表」误解。
13. **CORS / 代理**：开发期推荐 Vite proxy（`/api` → `http://127.0.0.1:8000`）；若前端直连 8000，
    后端已放行 5173/4173 的本机来源（见 1.6），不要去改后端 CORS 白名单。
14. **接口缺口（v1 已知，暂不加）**：没有 `GET /api/categories/{id}`（单条分类详情）、没有批量操作、
    没有图片上传/鉴权。分类下拉直接复用 `GET /api/categories` 的列表即可。

---

## 6. 本地启动与联调

### 6.1 后端启动

```bash
cd python/fastapi-demo

# 1) 准备 .env（首次）
cp .env.example .env   # 按需修改 DATABASE_URL
# 2) 建表（数据库需先手动建：CREATE DATABASE fastapi_demo DEFAULT CHARSET utf8mb4;）
make init-db
# 3) 写入演示数据（幂等，可重复执行）
./.venv/bin/python -m app.seed
# 4) 启动服务
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

seed 脚本输出示例（首次运行）：

```text
开始写入商品管理演示数据……
跳过已存在的分类：饮料（id=3）
新增分类：零食（id=7）
新增分类：乳品（id=8）
新增商品：可口可乐（id=6，价格 ¥3.50）
跳过已存在的商品：雪碧
...
完成：新增分类 2 个，新增商品 11 个，跳过已存在商品 1 个。
当前数据库共 3 个分类、14 个商品。
```

再次运行（幂等验证）：新增分类 0 个、新增商品 0 个，全部跳过，数据不重复。

### 6.2 回归命令

```bash
cd python/fastapi-demo
make check   # ruff check + ruff format --check + pytest（23 passed）
```

### 6.3 快速自测（curl）

```bash
BASE=http://127.0.0.1:8000

curl -s "$BASE/api/products?page=1&page_size=5"      # 列表
curl -s "$BASE/api/products/count"                   # 商品总数
curl -s "$BASE/api/categories"                       # 分类列表
curl -s "$BASE/api/categories/statistics"            # 各分类商品数

# CORS 预检（换 Origin 观察 access-control-allow-origin）
curl -s -i -X OPTIONS "$BASE/api/products" \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

---

## 附录 A：演示数据（seed 后）

分类（按统计接口的升序）：饮料 6 个商品 / 零食 4 个 / 乳品 4 个，共 **14** 个商品。

> 当前库中另有 3 条历史演示商品（矿泉水、可乐、雪碧，均在「饮料」下）；
> seed 脚本自带 12 条商品，其中「雪碧」按名称判定已存在会跳过，因此本次新增 11 条、最终 14 条。
> 在全新数据库上执行 seed 则是 3 个分类 + 12 个商品。

| 分类 | 商品 | 价格 | 库存 | 状态 |
| --- | --- | --- | --- | --- |
| 饮料 | 矿泉水（历史数据） | `3.50` | 20 | 上架 |
| 饮料 | 可乐（历史数据） | `3.00` | 100 | 上架 |
| 饮料 | 雪碧（历史数据） | `3.00` | 100 | 上架 |
| 饮料 | 可口可乐 | `3.50` | 120 | 上架 |
| 饮料 | 农夫山泉 | `2.00` | 200 | 上架 |
| 饮料 | 东方树叶 | `5.50` | 35 | 上架 |
| 零食 | 乐事薯片 | `6.50` | 60 | 上架 |
| 零食 | 奥利奥饼干 | `9.90` | 0 | **下架** |
| 零食 | 旺旺雪饼 | `5.80` | 45 | 上架 |
| 零食 | 三只松鼠坚果 | `28.80` | 12 | 上架 |
| 乳品 | 蒙牛纯牛奶 | `4.50` | 90 | 上架 |
| 乳品 | 光明酸奶 | `3.80` | 0 | **下架** |
| 乳品 | 伊利安慕希 | `7.50` | 66 | 上架 |
| 乳品 | 特仑苏 | `6.80` | 30 | 上架 |

## 附录 B：数据模型（数据库表）

`categories`（商品分类表）

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
| `shelf_status` | tinyint(1)/bool | NOT NULL，默认 1 | 是否上架 |
| `create_time` | datetime | NOT NULL，默认当前时间 | 创建时间 |

## 附录 C：变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-11-06 | 首次输出 11 个接口契约；新增 CORS 与 seed 演示数据说明 |
