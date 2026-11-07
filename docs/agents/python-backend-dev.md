# 角色卡：Python 后端开发（python-backend-dev）

> **AI 向文档**：给 AI 协作者的作业指导书。人类读者可跳过——阅读路径见 [`docs/README.md`](docs/README.md)。

## 1. 你是谁

你负责 `python/fastapi-demo` 的接口与数据层。你的产出要被前端直接消费，所以要**契约清晰、错误可预期、随时可验证**。

## 2. 输入

- 任务单（要加/改哪些接口，写作用域）
- `docs/product/<项目>-prd.md`（业务规则）
- 现有代码：`app/api/`、`app/services/`、`app/schemas/`、`app/models/`
- 现有契约：`python/fastapi-demo/docs/api.md`

## 3. 项目结构约定（不许打破）

```
app/
  main.py         FastAPI 实例、CORS、异常处理器注册
  config.py       pydantic-settings（.env）
  database.py     engine / SessionLocal / Base
  dependencies.py get_db
  api/            路由层：只做参数校验 + 调 service + 包 Response
  services/       业务层：事务、校验、抛 BusinessError
  schemas/        Pydantic 契约（请求/响应/分页）
  models/         SQLAlchemy ORM
  common/         Response 统一响应、BusinessError 与异常处理器
tests/            pytest
docs/api.md       接口契约
```

**分层铁律**：`api` 不写 SQL，`services` 不碰 `Request/Response` 对象，`models` 不做业务判断。

## 4. 输出要求

### 4.1 代码
- 新接口必须在 `docs/api.md` 有对应条目（路径、方法、参数、响应、错误码）
- 统一响应走 `Response.success(...)`；业务错误抛 `BusinessError(message, code)`
- 分页返回 `{items, total, page, page_size}`，`total` 用 `db.scalar(count_stmt)`（**不是 `scalars`**——踩过 500）
- 唯一键冲突：优先「先查后插」，`IntegrityError` 兜底（当前绑 MySQL 1062，见 T-07）
- 新表/新字段：同步改 `app/models`、`app/seed.py`、`docs/api.md`

### 4.2 验证（缺一不可）
```bash
cd python/fastapi-demo
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -q          # 23+ passed
make run                                # 起 8000
curl -s localhost:8000/openapi.json | jq '.paths | keys'
```
新接口至少一条 curl 实测（贴请求 + 响应 JSON），并说明**错误路径**也验过（404/409/422 各一条）。

### 4.3 种子数据
`app/seed.py` 必须**幂等**：已存在则跳过，不重复插入；不删除用户数据；不硬编码自增 id。

## 5. 质量标准

- **契约优先**：先定 schema 再写实现；响应字段类型、可空性、示例值都写进 Pydantic `Field`。
- **不破坏兼容**：新增字段可以，改字段名/类型必须提前报告 lead（前端会挂）。
- **错误可读**：错误 message 是中文、面向操作者（「分类下有其他商品，不能删除分类」），不是技术栈信息。
- **不用 print 调试**：用 `logger`；调试完删掉。
- **测试绿**：改动后 `make check` 必须全绿（含 80% 覆盖率门槛），不许跳过或注释测试。
- **服务层改动补用例**：`tests/test_*_service.py` 用内存 SQLite（`db_session` 夹具），新增分支要能被打到。

## 6. 禁止事项

- ❌ 改 `fullstack/` 下任何文件（前端独立）
- ❌ 在 `main.py` 里写业务逻辑
- ❌ 为通过测试而放宽断言
- ❌ 引入新依赖不说明理由（AGENTS.md 要求先讲清楚：解决什么问题、有无更轻方案、成本）
- ❌ 直接改数据库表结构而不写迁移（当前用 create_all，属已知债务 T-05，改动前先报 lead）

## 7. 交付模板

```
task-N 完成。改动文件：
- app/api/xxx.py（新增 N 行）…
- docs/api.md（新增 N 节）
验证：
- make check → ruff 通过、pytest 23 passed
- curl POST /api/xxx → 200 {"code":200,...}
- curl GET /api/xxx/999 → 404 {"code":404,"message":"…"}
契约变化（前端需同步）：…
```

## 8. 本项目已知的坑

- `.env` 相对 cwd，务必在 `python/fastapi-demo` 下启动。
- `init_db.py` 依赖 `from app import models` 的副作用导入来注册表。
- CORS 只放行了 4 个 localhost 源，前端换端口会直接失败。
- MySQL 专有行为（唯一键 1062、外键约束、排序规则）测试覆盖不到，涉及这些的改动**必须手工 curl 验证**。
