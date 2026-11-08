# My Agent 后端（backend）

My Agent 的 API 服务：对话会话与消息落库、SSE 流式回复、可切换的模型抽象（`fake` / OpenAI 兼容），配 Alembic 迁移、全局异常处理、lint / 测试 / CI。

> 商品与分类接口已随商品管理模块归档（`archive/product-admin/backend/`），现在只保留 `/api/conversations` 与三个探针。

## 技术栈

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | ≥ 3.11（本地 3.15，CI 3.12） | 代码语法 3.10 即可，dev 组工具要求 3.11 |
| FastAPI | 0.124.4 | Web 框架与依赖注入 |
| SQLAlchemy | 2.0.44 | ORM（`Mapped` / `mapped_column` 写法） |
| PyMySQL | 1.1.2 | MySQL 驱动 |
| httpx | 0.28 | 调用 OpenAI 兼容接口（`stream=True` 解析 SSE） |
| pydantic-settings | 2.12.0 | 读取 `.env` 配置 |
| MySQL | 8.x | 数据库，库名 `my_agent` |
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
│   ├── llm/              # 模型抽象：LLMClient 协议 + fake + OpenAI 兼容实现
│   ├── models/           # ORM 模型：conversations、messages
│   └── common/           # 统一响应 Response、业务异常与处理器
├── migrations/           # Alembic 迁移脚本（versions/ 下按 revision 链执行）
├── alembic.ini           # Alembic 配置（连接串不写这里，统一读 .env）
├── tests/                # 不依赖 MySQL 的自动化测试
├── Makefile              # 常用命令入口
├── pyproject.toml        # 依赖声明（[project] / [dependency-groups]）+ ruff / pytest 配置
├── uv.lock               # 依赖锁定（`uv sync` 按它安装，不要手改）
└── .env.example          # 环境变量模板
```

分层与调用方向（完整架构图与时序图见 [docs/how-it-works.md](../docs/how-it-works.md)）：

```text
api → services → models → database
 │        │
 │        └→ llm（LLMClient 协议：fake / openai 兼容）
 └→ schemas ← services
common（Response / BusinessError）被 api 与 main 复用
```

## 快速开始

```bash
cd backend

# 1. 依赖：uv 会按 uv.lock 建好 .venv 并装齐（含 dev 工具），不需要先手动 venv
uv sync

# 2. 配置：复制模板后改成自己的账号密码
cp .env.example .env
#    DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/my_agent?charset=utf8mb4

# 3. 建库（迁移只建表，不建库）
mysql -u root -p -e "CREATE DATABASE my_agent DEFAULT CHARSET utf8mb4;"

# 4. 迁移到最新表结构（等价于 alembic upgrade head，可重复执行）
uv run python -m app.init_db

# 5. 启动
uv run python -m uvicorn app.main:app --reload
```

打开 <http://127.0.0.1:8000/docs> 查看接口文档。

> 没装 uv？`brew install uv` 或 `curl -LsSf https://astral.sh/uv/install.sh | sh`。不打算用 uv 时，`uv export --format requirements-txt --no-hashes > /tmp/req.txt` 可以导出成 pip 能用的依赖清单（属临时方案，版本以 uv.lock 为准）。

## 接入真实模型

默认 `LLM_PROVIDER=fake`：不联网、不需要 key，回复形如 `[fake] 收到：<你的话>`，方便本地开发与 CI。

要用真实模型（下面以 DeepSeek 为例），在 `backend/.env` 里改这四行，然后重启服务：

```bash
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-你的key
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=60      # 流式按整条回复计时，30s 对长回答偏紧
```

容器部署时把这四行写到**仓库根**的 `.env`（`docker-compose.yml` 会把它们传给 `backend`），然后 `docker compose up -d backend`。

几点说明：

- 任何 OpenAI 兼容服务都能用，换 `LLM_BASE_URL` 与 `LLM_MODEL` 即可（OpenAI、硅基流动、vLLM 等）。
- key 只放 `.env`（`.gitignore` 已忽略），不要写进代码、提交或打进镜像；`Settings` 用 `SecretStr` 并在校验错误里隐藏输入值。
- `LLM_PROVIDER=openai` 时缺任一项配置，服务**启动阶段**就会报 `LLM_PROVIDER=openai 时必须配置：...`，不会拖到第一次请求。
- 上游故障会被翻译成固定文案（402 余额不足、401/403 鉴权失败、429 限流、超时 504），原始报错不透传给前端，详见 [`docs/api.md`](../docs/api.md) §4.6。
- 若 shell 里的 `NO_PROXY` 写成 `[::1]` 这类 httpx 解析不了的形式，客户端会自动退化为忽略环境代理，只在日志里留一条 warning。

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
make revision m="给会话加置顶字段"

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

7 个对话操作 + 3 个运维/根路径：会话 5（新建/列表/详情/改名/删除）、消息 2（同步、SSE 流式）、运维 3（`GET /`、`GET /healthz`、`GET /readyz`）。

**完整契约（参数、响应字段、错误文案、示例）在 [`docs/api.md`](../docs/api.md)** —— 那是唯一来源，本文件不再重复维护。

统一响应格式：`{"code": 200, "message": "请求成功", "data": ...}`；业务异常由全局处理器转成同样的外壳，`code` 与 HTTP 状态码一致。

## 测试

```bash
make test        # 75 个用例 + 覆盖率门槛（80%），全程不连 MySQL
make check       # lint + 测试，提交前跑这个
```

两类用例共用 `tests/conftest.py` 里的占位 `DATABASE_URL`：

- **接口层**（`test_health` / `test_errors` / `test_chat_api`）：`TestClient` 直连 ASGI 应用，
  用 `dependency_overrides` 把 `get_db` / `get_llm` 换成内存 SQLite 与假模型，不连库、不联网
- **服务层**（`test_chat_service` / `test_llm`）：`db_session` 夹具给**内存 SQLite**，
  真跑 insert/select/update/delete、上下文截断、事务回滚、SSE 事件序列；`httpx.MockTransport` 模拟上游

覆盖率门槛写在 `pyproject.toml` 的 `[tool.coverage.report] fail_under = 80`，
`app/init_db.py` 是手工执行的脚本，已 `omit` 掉。当前实测 91%（75 个用例）。

**没有覆盖到的**：MySQL 专有行为——外键 `ON DELETE CASCADE` 的真实级联、`utf8mb4` 排序规则、并发下的事务可见性。
这类用例需要真实 MySQL（或 testcontainers），属于后续工作（见 `docs/TECHNICAL_DEBT.md` T-04）。

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

- 模型调用是同步阻塞的（`httpx.Client`），单个请求占用一个工作线程；高并发下需要换成异步客户端或线程池。
- 迁移写库需要真实 MySQL：`make check-migration` 只在本机跑，CI 目前不校验迁移一致性。
- `Response.data` 是 `Any`，OpenAPI 里看不到具体结构；可为每个接口声明具体 `response_model`。
- 非流式与流式两条路径记录的 `model` 标签不一致：同步存上游返回的模型名（如 `deepseek-flash`），流式存配置名（如 `deepseek-chat`）。

- 上下文只带最近 20 条消息（`CONTEXT_LIMIT`），没有摘要压缩，长对话会丢早期信息。
- 容器化部署见根目录 [`docs/deploy.md`](../docs/deploy.md)；镜像未进 CI，构建失败只能在本地暴露。
- 仓库里曾存在 `python/.venv` 旧虚拟环境（目录迁移遗留），建议删掉只保留 `backend/.venv`。

## 相关文档

- [接口契约](../docs/api.md)：参数、响应字段、错误文案、真实示例
- [系统怎么跑起来](../docs/how-it-works.md)：分层理由、请求时序、数据模型、新增资源的步骤
- [工具链](../docs/toolchain.md)：uv / ruff / pytest / Alembic 各自解决什么问题
