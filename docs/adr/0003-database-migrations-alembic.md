# ADR-0003 用 Alembic 接管表结构演进

> **AI 向文档**：架构决策记录，人与 AI 共读；每条决策的「为什么」是重点。总入口见 [`../README.md`](../README.md)。

- 状态：**已采纳**
- 日期：2026-11-07
- 相关：[TECHNICAL_DEBT T-05](../TECHNICAL_DEBT.md)、[REUSE_CANDIDATES §2](../archive/REUSE_CANDIDATES.md)
- 取代：`app/init_db.py` 里的 `Base.metadata.create_all(bind=engine)`

## 背景

建表一直靠 `Base.metadata.create_all`：它只在表**不存在**时建，不会给已有表加列、改类型、加索引，也不留版本记录。加一个字段就要手工 SQL，回滚全靠记忆——这是上线前的硬门槛（T-05）。

数据库里已有真实数据（3 个分类 / 14 个商品），不能重建。

## 决定

引入 **Alembic 1.20.1**（SQLAlchemy 官方迁移工具，MIT），按以下方式落地：

1. `migrations/versions/` 存放版本化脚本，`alembic.ini` **不写连接串**，由 `migrations/env.py` 从 `app.config.settings`（即 `.env` 的 `DATABASE_URL`）读取。
2. 首个 revision `2a89b3237f54`（`initial schema`）用 `--autogenerate` 对一个**空库**生成，再与本机已有库逐表比对 `SHOW CREATE TABLE`，确认完全一致。
3. 已有库用 `alembic stamp head` 接管：只写 `alembic_version`，不执行 DDL、不动数据。
4. `app/init_db.py` 从「`create_all`」改为「`command.upgrade(config, "head")`」，命令名与 `make init-db` 保持不变。
5. `make check` 保持 lint + 测试（不需要数据库），迁移一致性用独立的 `make check-migration` 校验，避免 CI 因缺 MySQL 变红。

## 代价

- 多一个运行时依赖（`alembic==1.20.1`，连带 `Mako`）。
- 改模型后多一步「生成 + 人工 review + 应用」。
- autogenerate 有盲区：表/列**改名**会被识别为「删旧的建新的」（丢数据），必须人工核对生成的脚本。
- CI 目前不校验迁移一致性（要加 MySQL service，属后续事项）。

## 被否掉的方案

| 方案 | 否掉的原因 |
|---|---|
| 继续 `create_all` + 手工 SQL | 无版本、无回滚、无法自动化，问题会随字段增多放大 |
| 每次改动重建库 | 有真实数据，不现实 |
| 只保留 SQL 文件（无工具） | 靠人执行顺序，无「已应用到哪一版」的记录 |

## 复评触发条件

- 出现多人并行改 schema，需要分支合并策略时 → 评估 Alembic 分支/多 head 流程。
- 需要 CI 校验迁移时 → 给 workflow 加 MySQL service 并跑 `alembic upgrade head` + `alembic check`。
- 引入分库/多租户 → 需要按库 stamp 与多环境配置，届时扩充 `env.py`。
