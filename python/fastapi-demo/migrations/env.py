"""Alembic 运行环境：从 app.config 读取连接串，以 app 的 ORM 元数据做 autogenerate。

设计要点：
1. 连接串只有一处来源（`.env` 的 DATABASE_URL），不在 alembic.ini 里重复写死。
2. 必须 `from app import models`，否则 Base.metadata 为空，autogenerate 会生成「删表」。
3. `compare_type=True` 让字段类型变更也能被 autogenerate 发现。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app import models  # noqa: F401  # 导入即注册模型，autogenerate 依赖这次副作用
from app.config import settings
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """优先用 -x db_url=... 覆盖，便于对测试库执行迁移，其余情况读 .env。"""
    override = context.get_x_argument(as_dictionary=True).get("db_url")
    return override or settings.database_url


def run_migrations_offline() -> None:
    """离线模式：只输出 SQL，不连接数据库。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：自己建 Engine（不用 engine_from_config，避免从 ini 读连接串）。"""
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
