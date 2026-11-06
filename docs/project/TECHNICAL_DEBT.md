# TECHNICAL_DEBT — 当前问题、风险与优化建议

> 调研时间：2026-11-06 · 基线：`4be025b`
> 评级：**P0** = 阻塞后续开发 / 会反复咬人，**P1** = 应尽快处理，**P2** = 可延后。成本：**S**（<半天）/ **M**（1–2 天）/ **L**（>2 天）。
> 每条都给出证据位置；**未验证的推断会标注「待验证」**。

## 0. 汇总

| ID | 类别 | 问题 | 优先级 | 成本 |
|---|---|---|---|---|
| T-01 | 协作 | `AGENTS.md`、`docs/prompts/` 未提交，规则资产只在工作区 | P0 | S |
| T-02 | 前端 | ~~零静态检查（无 ESLint / Prettier）~~ ✅ 轻量档门禁已落地 | P0 | S |
| T-03 | 前端 | 零单测、CI 不覆盖前端，按轻量档补 | P0 | S |
| T-04 | 后端 | 测试完全不连库，SQL/约束/事务路径没有任何自动化覆盖 | P1 | M |
| T-05 | 数据库 | ~~无迁移工具，靠 `create_all` 建表~~ ✅ 已由 Alembic 接管 | P1 | M |
| T-06 | 后端 | `Response.data: Any`，OpenAPI 看不到真实结构 | P1 | M |
| T-07 | 后端 | 用 MySQL 私有错误码 1062 判重名，换库即失效 | P1 | S |
| T-08 | 后端 | 配置只有 1 个字段、`.env` 按 cwd 相对查找、无环境区分 | P1 | S |
| T-09 | 部署 | 完全没有容器化 / 反代 / 健康检查 / 发布脚本 | P1 | L |
| T-10 | 前端 | API 基址硬编码 `/api`，生产环境只能靠同域反代 | P1 | S |
| T-11 | 验收 | E2E 脚本依赖本地起服务、且会写真实库（曾误删商品） | P1 | M |
| T-12 | 环境 | 本机 Python 3.15 / CI 3.12，无 `.python-version` | P1 | S |
| T-13 | 环境 | `gh` 凭据未接到 git，push 每次要临时绕过 | P1 | S |
| T-14 | 后端 | 错误文案三套（"商品不存在"/"未找到商品"）、错误通道两条 | P2 | S |
| T-15 | 后端 | 分页 total 与 items 两次独立查询，并发下可能不一致 | P2 | S |
| T-16 | 后端 | 关键字搜索 `LIKE '%kw%'` 无法走索引 | P2 | M |
| T-17 | 后端 | 无鉴权、CORS 写死 localhost、`allow_methods=["*"]` | P2 | L |
| T-18 | 数据 | `create_time` 用 naive `datetime.now`，无时区语义 | P2 | S |
| T-19 | 文档 | `docs/README.md` 定位过期；`app/README.md` 与项目 README 重复 | P2 | S |
| T-20 | 文档 | `docs/design/images/` 与 `docs/product-admin/images/` 同名不同源，易混 | P2 | S |
| T-21 | 前端 | Element Plus 打成 943KB 单 chunk，首屏成本偏高 | P2 | M |
| T-22 | 后端 | 分类改名不 `strip()` 空白，可存入全空格名称 | P2 | S |
| T-23 | 后端 | 日志无统一配置、无 request id，排障靠 print 级信息 | P2 | M |
| T-24 | 环境 | Docker 守护进程未运行、无 compose 子命令 | P2 | S |
| T-25 | 卫生 | `.DS_Store`、`__pycache__`、`dist/`、`.ruff_cache` 残留在工作区 | P2 | S |

## 1. 协作与规则资产

### T-01 `AGENTS.md` / `docs/prompts/` 未入库（P0 · S）
- **证据**：`git status` → `?? AGENTS.md`、`?? docs/prompts/`、`?? docs/PROJECT_STATUS.md`。
- **影响**：这是整个项目的「AI 协作契约」。一旦换机器或协助者接手，规范与 7 阶段提示词全部消失。
- **建议**：单独一个 `docs: 补充 AI 协作规范与分阶段提示词` 提交，并把 `docs/PROJECT_STATUS.md` 一起纳入。

## 2. 前端质量（最大空白）

### T-02 零静态检查（P0 · S）—— ✅ 已于 2026-11-07 解决
- **证据（当时）**：仓库内不存在 `eslint.config.*` / `.eslintrc*` / `.prettierrc*` / `biome.json`（`find` 实测为空）。
- **影响**：后端有 ruff 兜底，前端全靠 `vue-tsc --noEmit`；类型之外的问题（未定义变量、模板里写错指令、重复声明）无人拦。
- **解决**（按 [ADR-0002](../adr/0002-frontend-quality-gate-lite.md)「轻量档」）：`eslint@10.14.0` flat config（`@eslint/js` recommended + `typescript-eslint` recommended + `eslint-plugin-vue` flat/essential，**不开 type-aware**）+ Prettier 3（不进 CI 阻断）；CI 新增 `frontend` job（`pnpm build` + `pnpm lint`）。存量代码只报 2 个 error，已修。
- **遗留**：未启用 type-aware 规则，`any` 泛滥一类问题仍靠 review 兜底。

### T-03 零单元测试（P0 · S）—— CI 覆盖已补，单测未做
- **证据**：`fullstack/product-admin` 下无 `tests/`、无 `vitest.config.*`（CI 覆盖已于 2026-11-07 补上，见 T-02）。
- **影响**：前端唯一的质量网是 18 项 E2E，跑一次要装 Chrome、起两个服务、改动真实数据库；改一个组件无法快速验证。
- **建议**（轻量档）：Vitest 只覆盖 `src/api`（错误映射）、`src/utils`（格式化）两类纯逻辑，**不写组件快照、不设覆盖率门槛**；CI 增加前端 job（`pnpm install --frozen-lockfile && pnpm build && pnpm lint`）。组件层继续由 18 项 E2E + 人工验收兜底。

## 3. 后端

### T-04 测试不连库（P1 · M）
- **证据**：`python/fastapi-demo/tests/conftest.py` 注入的是占位 DSN（`test:test@127.0.0.1:3306`），用例只覆盖 422/400/404 这类「产生 SQL 之前」的路径；23 个用例 0.38s 跑完。
- **影响**：分页 500 那类 bug（`scalars` vs `scalar`）之所以能上线，正是因为这条路径没测试。唯一键冲突、事务回滚、联表统计、PATCH 语义全无覆盖。
- **建议**：二选一——(a) `dependency_overrides` 把 `get_db` 换成 SQLite 内存库（快，但 MySQL 方言差异会失真）；(b) testcontainers/本地 MySQL + 每用例事务回滚（准，慢）。推荐 (b) 作为「仓储层集成测试」小集合，(a) 作为日常快速回归。

### T-05 无迁移工具（P1 · M）—— ✅ 已于 2026-11-07 解决
- **证据（当时）**：`app/init_db.py:14` `Base.metadata.create_all(bind=engine)`；仓库无 `alembic.ini` / `migrations/`。
- **影响**：`create_all` 只建表不改表。加字段、改类型、加索引都得手工 SQL，且没有回滚。
- **解决**：引入 Alembic 1.20.1（[ADR-0003](../adr/0003-database-migrations-alembic.md)）。首个 revision `2a89b3237f54` 对空库 autogenerate 生成、与本机库逐表 `SHOW CREATE TABLE` 比对一致后 `stamp head` 接管；`app/init_db.py` 改为执行 `upgrade head`；新增 `make migrate` / `make revision` / `make check-migration`。
- **遗留**：CI 仍未校验迁移一致性（需 MySQL service）。

### T-06 `Response.data: Any`（P1 · M）
- **证据**：`app/common/response.py:12` `data: Any = None`；`app/main.py:18` 又把 422 的 `model` 指向同一个 `Response`。
- **影响**：`/openapi.json` 里所有响应的 `data` 都是空 schema，前端类型只能手写（现由 `src/types/api.ts` 手工维护，必然漂移）。
- **建议**：`Response[T](BaseModel, Generic[T])` + 每个接口声明 `response_model=Response[ProductResponse]`；前端用 `openapi-typescript` 生成类型，取代手写。

### T-07 依赖 MySQL 私有错误码（P1 · S）
- **证据**：`app/services/category_service.py:38` 与 `:68` 均为 `isinstance(exc, IntegrityError) and exc.orig.args[0] == 1062`。
- **影响**：把「重名」这一业务语义绑死到 MySQL 驱动细节；换 PG/SQLite 即失效，且无法区分「哪一个唯一键」冲突。
- **建议**：写入前先 `select` 查重（业务层显式判断），或在 `IntegrityError` 里匹配约束名；`1062` 只作为兜底。

### T-08 配置体系过薄（P1 · S）
- **证据**：`app/config.py:8-13` 只有 `database_url` 一个字段，`env_file=".env"` 是相对路径（注释里也承认「以运行命令时所在的目录为基准」）。
- **影响**：换目录启动就读不到配置；没有 dev/test/prod 区分，CORS、日志级别、数据库都写死。
- **建议**：`Settings` 增加 `env`、`cors_origins`、`log_level`；`env_file` 用绝对路径（`Path(__file__).parent.parent / ".env"`）；提供 `.env.development` / `.env.production` 模板。

### T-14 错误文案与通道不统一（P2 · S）
- **证据**：`app/api/products.py:81` 抛 `HTTPException(404, "商品不存在")`；`app/services/product_service.py:133` 抛 `BusinessError("未找到商品", 404)`；`:165` 又是「商品不存在」。
- **影响**：同一语义三种文案；且详情接口走 HTTPException、其余走 BusinessError，两套处理器分别兜底，容易再分叉。
- **建议**：全部收敛到 `BusinessError`，文案统一为「商品不存在」，并在 `docs/api.md` 里定义错误码表。

### T-15 分页两次查询（P2 · S）
- **证据**：`app/services/product_service.py` 中先 `db.scalar(count_stmt)` 再查 items。
- **影响**：并发写入时 `total` 与 `items` 可能对不上（页码越界、总数少 1）。
- **建议**：同事务内两次查询（当前已是同一 Session，风险低），或用窗口函数 `COUNT(*) OVER()` 一次拿全；至少在文档里写明这是「最终一致」的近似值。

### T-16 模糊搜索无索引（P2 · M）
- **证据**：`app/services/product_service.py:51` `Product.name.contains(keyword, autoescape=True)` → `LIKE '%kw%'`。
- **影响**：数据量上万后全表扫描；现在 14 行的库完全无感，属于「等到有感觉时已经晚了」的问题。
- **建议**：短期不加索引（前缀匹配 `LIKE 'kw%'` 才可用索引）；真要做搜索时上 MySQL 全文索引或 Meilisearch，不要在中文字段上硬拼 `LIKE`。

### T-17 无鉴权 + CORS 写死（P2 · L）
- **证据**：`app/main.py:22-36` `ALLOWED_ORIGINS` 硬编码 4 个 localhost，`allow_methods=["*"]`；全仓库无 auth 代码。
- **影响**：本地练习无妨，**一旦部署到公网就是裸奔**（任何人可增删商品）。
- **建议**：部署前必须加最小鉴权（哪怕是单一 API Key / HTTP Basic），CORS 来源改为配置项，且 `allow_methods` 收敛。

### T-22 分类改名不 strip（P2 · S）
- **证据**：`app/services/category_service.py` 的 `update_category` 直接使用入参，无 `strip()`；创建路径有全空白校验。
- **影响**：可以把分类改成 `"   "`，前端显示为空白行。
- **建议**：与创建路径共用同一个 `normalize_name()` 校验。

### T-23 日志无统一配置（P2 · M）
- **证据**：`app/common/exceptions.py:23` 用模块级 `logger`，但项目无 `logging.config`/`dictConfig`，也无 request id。
- **影响**：线上排障只能看 uvicorn 默认访问日志 + 零散 traceback；一次请求的多条日志无法串联。
- **建议**：`logging.dictConfig`（控制台 + 文件双 handler）、中间件注入 `X-Request-ID`，JSON 格式便于后续采集。

## 4. 数据库与数据

### T-18 naive datetime（P2 · S）
- **证据**：`app/database.py` `create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)`。
- **影响**：存的是本机本地时间，无时区；换时区部署/多机写入会出现排序错乱。
- **建议**：改 `DateTime(timezone=True)` + `datetime.now(timezone.utc)`，展示层再转本地时区。

### T-05 已覆盖的「无迁移」另见上。

## 5. 部署与交付

### T-09 零部署能力（P1 · L）
- **证据**：仓库无 `Dockerfile`、`docker-compose.yml`、反代配置、部署脚本；`.github/workflows/` 只有 `ci.yml`。
- **影响**：AGENTS.md 要求「第一天就考虑部署」，目前一条都没有。阶段 4 会集中补，但现在连「后端怎么在生产跑」都没答案。
- **建议**：按 `docs/prompts/4` 的产出要求做；最小闭环 = 多阶段 Dockerfile + compose（api + mysql）+ Caddy 反代 + `/healthz`。

### T-10 前端 API 基址硬编码（P1 · S）
- **证据**：`src/api/client.ts` `baseURL: '/api'`；`vite.config.ts` 用 proxy 转发。
- **影响**：开发期很舒服，但生产构建里 `'/api'` 是相对路径——必须由同域反代兜住，否则前端无法独立部署到 CDN/静态托管。
- **建议**：`baseURL: import.meta.env.VITE_API_BASE ?? '/api'`，并补 `.env.example`。

### T-11 E2E 脚本会写真实库（P1 · M）
- **证据**：`scripts/acceptance.mjs` 直接对 `http://127.0.0.1:8000` 增删改；上一轮它曾误删一台真实商品（「东方树叶」），靠手工重灌数据恢复。
- **影响**：验收 = 破坏数据。多跑几次，库里就有 `E2E测试商品` 之类的残留。
- **建议**：脚本内所有写操作加唯一前缀并在 `finally` 清理（已有部分）；更彻底的做法是让后端支持「测试专用 schema」或由脚本先 `pg_dump`/快照。

### T-24 Docker 不可用（P2 · S）
- **证据**：`docker --version` 有（29.9.2），但 `docker info` 报 `failed to connect to the docker API at unix:///var/run/docker.sock`，`docker compose version` → `unknown command`。
- **影响**：阶段 4 的容器化没有执行环境。
- **建议**：装 Docker Desktop / OrbStack，或评估 `colima`（轻量、brew 可装）。装之前先确认磁盘与内存占用。

## 6. 环境与工具链

### T-12 Python 版本漂移（P1 · S）
- **证据**：本机 `python3 -V` = 3.15.0；`.github/workflows/ci.yml` 用 `3.12`；仓库无 `.python-version`、`pyproject.toml` 也只配工具不声明 `requires-python`。
- **影响**：本机能过、CI 挂（或反之）的经典来源；尤其 pydantic/SQLAlchemy 这种对解释器版本敏感的组合。
- **建议**：加 `.python-version`（写 3.12 或 3.13，别追 3.15），`pyproject.toml` 补 `requires-python = ">=3.12"`，CI 与本机统一。

### T-13 gh 凭据未接到 git（P1 · S）
- **证据**：`git config --get-all credential.helper` 只有 `osxkeychain`；上次 push 需 `-c credential.helper='!gh auth git-credential'` 才成功。
- **影响**：每次 push 都要手工绕过，容易误以为网络故障。
- **建议**：`gh auth setup-git`（改 `~/.gitconfig`，属于全局配置，需你确认后执行）。

## 7. 文档与仓库卫生

### T-19 文档定位重复/过期（P2 · S）
- **证据**：`docs/README.md` 仍自称「存放跨项目学习资料」，但 `docs/` 下实际放的是 product/design/product-admin 三套**项目交付文档**；`python/fastapi-demo/app/README.md`（9 行目录说明）与项目级 README 的「目录结构」章节内容重叠。
- **建议**：`docs/README.md` 改成文档索引（学习笔记 / 项目文档 / 流程规范 三个分区）；删掉 `app/README.md` 或把它改成「本目录只讲分层职责，细节见 ../README.md」。

### T-20 两套同名设计图（P2 · S）
- **证据**：`docs/design/images/01-product-list.png`（设计稿导出）与 `docs/product-admin/images/01-product-list.png`（实机截图）同名；`docs/design/mockups/*.html` 又是第三份。
- **影响**：review 时极易贴错图；也让人分不清「哪张是设计、哪张是实现」。
- **建议**：文件名加前缀（`design-01-*.png` / `shot-01-*.png`），或在各自 README 顶部放一张对照说明。

### T-25 工作区残留（P2 · S）
- **证据**：`./.DS_Store`、`python/.DS_Store`、多处 `__pycache__`、`fullstack/product-admin/dist/`、`.ruff_cache/`（均已被 `.gitignore` 忽略，不会入库）。
- **影响**：无功能影响，但 `find`/搜索噪音大，且 `dist/` 存在会让人误以为构建产物需要提交。
- **建议**：`make clean` 或在 README 注明；不必特意清理。

## 8. 潜在风险（不是缺陷，但会咬人）

| 风险 | 说明 | 触发时机 |
|---|---|---|
| 仓库 Public | 全历史已核对无 `.env` / 密钥；但后续每次提交都需自检 | 任何提交 |
| 单机依赖 MySQL 8.4 | 迁移到 CI/容器后版本差异（8.0 vs 8.4）会带来行为差异 | 上 CI 集成测试时 |
| `pnpm` 12 的 build script 白名单 | 新装依赖（如 esbuild）可能被静默跳过安装脚本 | 新增依赖时 |
| Element Plus 体积 | 943KB 单 chunk，弱网首屏慢 | 真正上线时 |
| 没有 ADR | 技术决策散落在 `docs/*.md` 与对话里，事后难以追溯 | 决策增多后 |

## 9. 建议的处理顺序

1. **本周（P0）**：T-02 ✅ 前端 lint + CI（已完成）→ T-03 前端单测 → T-12 统一 Python 版本。
2. **阶段 3（架构/基建）**：T-06 泛型响应、T-08 配置分层、T-04 集成测试小集合（T-05 Alembic 已完成）。
3. **阶段 4（部署）**：T-09 容器化与反代、T-10 API 基址、T-17 最小鉴权、T-24 装 Docker。
4. **持续**：T-11 验收脚本隔离、T-15/T-16 查询优化、T-19/T-20 文档整理。
