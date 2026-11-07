# fastapi-demo

FastAPI + SQLAlchemy 的商品/分类接口练习项目：覆盖增删改查、分页与模糊查询、联表查询、分组统计、统一响应与全局异常处理，并配套 lint、测试与 CI。

## 技术栈

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | ≥ 3.11（本地 3.15，CI 3.12） | 代码语法 3.10 即可，dev 组工具要求 3.11 |
| FastAPI | 0.124.4 | Web 框架与依赖注入 |
| SQLAlchemy | 2.0.44 | ORM（`Mapped` / `mapped_column` 写法） |
| PyMySQL | 1.1.2 | MySQL 驱动 |
| pydantic-settings | 2.12.0 | 读取 `.env` 配置 |
| MySQL | 8.x | 数据库，库名 `fastapi_demo` |
| 依赖管理 | uv 0.13.4（`pyproject.toml` + `uv.lock`） | 不用 requirements.txt，`.venv` 由 `uv sync` 维护 |
| ruff / pytest / pre-commit | 见 `pyproject.toml` 的 `[dependency-groups].dev` | 工程化工具链 |

## 目录结构

```text
fastapi-demo/
├── app/
│   ├── main.py           # 应用入口：注册路由与 5 个全局异常处理器
│   ├── config.py         # Settings：读取 .env 中的 DATABASE_URL
│   ├── database.py       # Engine、Session 工厂、Base（公共 id / create_time）
│   ├── dependencies.py   # get_db：每个请求一个 Session，用完关闭
│   ├── init_db.py        # 把库升到最新迁移版本：python -m app.init_db
│   ├── api/              # 接口层：只做参数接收、调用 service、包装响应
│   ├── schemas/          # 数据契约：入参校验与出参序列化
│   ├── services/         # 业务层：校验、事务提交/回滚、ORM 读写
│   ├── models/           # ORM 模型：categories、products
│   └── common/           # 统一响应 Response、业务异常与处理器
├── migrations/           # Alembic 迁移脚本（versions/ 下按 revision 链执行）
├── alembic.ini           # Alembic 配置（连接串不写这里，统一读 .env）
├── tests/                # 不依赖 MySQL 的自动化测试
├── Makefile              # 常用命令入口
├── pyproject.toml        # 依赖声明（[project] / [dependency-groups]）+ ruff / pytest 配置
├── uv.lock               # 依赖锁定（`uv sync` 按它安装，不要手改）
└── .env.example          # 环境变量模板
```

分层与调用方向（完整架构图与时序图见 [docs/how-it-works.md](../../docs/how-it-works.md)）：

```text
api → services → models → database
 │        │
 └→ schemas ← services
common（Response / BusinessError）被 api 与 main 复用
```

## 快速开始

```bash
cd python/fastapi-demo

# 1. 依赖：uv 会按 uv.lock 建好 .venv 并装齐（含 dev 工具），不需要先手动 venv
uv sync

# 2. 配置：复制模板后改成自己的账号密码
cp .env.example .env
#    DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/fastapi_demo?charset=utf8mb4

# 3. 建库（迁移只建表，不建库）
mysql -u root -p -e "CREATE DATABASE fastapi_demo DEFAULT CHARSET utf8mb4;"

# 4. 迁移到最新表结构（等价于 alembic upgrade head，可重复执行）
uv run python -m app.init_db

# 5. 启动
uv run python -m uvicorn app.main:app --reload
```

打开 <http://127.0.0.1:8000/docs> 查看接口文档。

> 没装 uv？`brew install uv` 或 `curl -LsSf https://astral.sh/uv/install.sh | sh`。不打算用 uv 时，`uv export --format requirements-txt --no-hashes > /tmp/req.txt` 可以导出成 pip 能用的依赖清单（属临时方案，版本以 uv.lock 为准）。

## 常用命令

```bash
make install      # 按 uv.lock 装齐依赖（含 ruff / pytest / pre-commit）
make lock         # 改了 [project] 的依赖后重新解析 uv.lock
make run          # 启动开发服务器（热重载）
make migrate      # 应用迁移（alembic upgrade head）
make init-db      # 同上，保留旧命令名
make revision m="新增 xxx 表"  # 按模型改动生成迁移文件
make check-migration           # 校验模型与迁移脚本一致（需连库）
make test         # 运行测试并检查覆盖率（不需要 MySQL）
make lint         # 静态检查，只报告不改文件
make fmt          # 自动修复导入顺序并格式化
make check        # 提交前自检：lint + 测试
```

## 数据库迁移（Alembic）

表结构由 `migrations/versions/` 下的版本化脚本定义，**不要再直接改库**。

```bash
# 改了 app/models/ 之后：生成迁移文件（连的就是 .env 里的库）
make revision m="为商品增加备注字段"

# 生成后务必人工 review：autogenerate 对「表/列改名」识别为「删旧的 + 建新的」，会丢数据
git diff migrations/versions/

# 应用到数据库（可重复执行，已是最新则什么都不做）
make migrate

# 确认模型与脚本没有漂移（需要能连上 MySQL）
make check-migration
```

- 连接串只有一处来源：`app/config.py` 读 `.env` 的 `DATABASE_URL`；`alembic.ini` 里**故意不写** `sqlalchemy.url`。
- 想在别的库上试跑：`alembic -x db_url=mysql+pymysql://user:pass@host:3306/other_db upgrade head`。
- 已有库第一次接入：确认表结构与脚本一致后 `alembic stamp head`，只写 `alembic_version`，不动数据。
- `make check` 仍然只跑 lint + 测试（不需要数据库），CI 依赖这一点。

## 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 健康检查 |
| POST | `/api/categories` | 新增分类，重名返回 409 |
| GET | `/api/categories` | 分类列表（ID 倒序） |
| PATCH | `/api/categories/{category_id}` | 修改分类名称 |
| DELETE | `/api/categories/{category_id}` | 删除分类，分类下有商品时返回 409 |
| GET | `/api/categories/statistics` | 各分类商品数量（含 0 的分类） |
| POST | `/api/products` | 新增商品，分类不存在时返回 400 |
| GET | `/api/products` | 分页 + 关键词 + 分类筛选 |
| PATCH | `/api/products/{product_id}` | 局部修改商品 |
| DELETE | `/api/products/{product_id}` | 删除商品 |
| GET | `/api/products/count` | 商品总数 |
| GET | `/api/products/{product_id}` | 商品详情，不存在返回 404 |

统一响应格式：`{"code": 200, "message": "请求成功", "data": ...}`；业务异常由全局处理器转成同样的外壳，`code` 与 HTTP 状态码一致。

## 测试

```bash
make test        # 50 个用例 + 覆盖率门槛（80%），全程不连 MySQL
make check       # lint + 测试，提交前跑这个
```

两类用例共用 `tests/conftest.py` 里的占位 `DATABASE_URL`：

- **接口层**（`test_health` / `test_schemas` / `test_errors` / `test_api_validation`）：
  `TestClient` 直连 ASGI 应用，用例停在参数校验与异常处理阶段，`create_engine` 惰性所以不会连库
- **服务层**（`test_category_service` / `test_product_service`）：`db_session` 夹具给**内存 SQLite**，
  真跑 insert/select/update/delete、分页、关键词与分类筛选、删除保护，验证的是 SQL 与业务分支

覆盖率门槛写在 `pyproject.toml` 的 `[tool.coverage.report] fail_under = 80`，
`app/init_db.py` 与 `app/seed.py` 是手工执行的脚本，已 `omit` 掉。当前实测 85%。

**没有覆盖到的**：MySQL 专有行为——唯一键冲突的 `1062` 分支、外键约束、`utf8mb4` 排序规则。
这类用例需要真实 MySQL（或 testcontainers），属于后续工作。

## 工程规范

| 项 | 现状 | 命令 |
|---|---|---|
| 代码风格 | ruff（lint + format，行宽 100） | `make lint` / `make fmt` |
| 导入顺序 | isort 规则，`app` 视为一方包 | 随 `make fmt` 自动修复 |
| 提交前检查 | pre-commit：ruff、尾随空格、yaml/toml、密钥检测 | `uv sync && uv run pre-commit install` |
| CI | GitHub Actions：ruff + format + pytest（含覆盖率，Python 3.12） | `.github/workflows/ci.yml` |
| 配置管理 | `.env` 不入库，模板 `.env.example` | `cp .env.example .env` |
| 依赖锁定 | 全部 `==` 固定版本 | — |

## 已知限制与后续计划

- 唯一约束冲突判断依赖 MySQL 错误码 `1062`（`app/services/category_service.py`、`product_service.py`），换数据库需调整。
- 迁移写库需要真实 MySQL：`make check-migration` 只在本机跑，CI 目前不校验迁移一致性。
- `Response.data` 是 `Any`，OpenAPI 里看不到具体结构；可为每个接口声明具体 `response_model`。
- 列表接口的 `total` 与 `items` 是两次查询，极端并发下可能不一致。
- 没有 Docker / 部署脚本，目前面向本地学习。
- 仓库里存在两个虚拟环境（`python/.venv` 与 `python/fastapi-demo/.venv`），建议只保留项目内的 `.venv`。

## 相关文档

- [目录职责速查](app/README.md)
