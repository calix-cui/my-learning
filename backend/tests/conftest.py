"""测试公共配置。

app.config.Settings 的 database_url 没有默认值，缺少配置时 import app 直接抛校验错误。
这里先注入一个占位连接串，再导入应用代码——顺序不能颠倒。

两类测试的数据库策略：
- 接口层（TestClient）：create_engine 是惰性的，只要请求停在参数校验/异常处理阶段就不会连库；
- 服务层：用 `db_session` 夹具给内存 SQLite，验证真实的增删改查与分页，不依赖本机 MySQL。
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://test:test@127.0.0.1:3306/fastapi_demo_test?charset=utf8mb4",
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  导入即把模型注册到 Base.metadata
from app.database import Base


@pytest.fixture()
def db_session() -> Session:
    """内存 SQLite 会话：服务层测试不依赖 MySQL，跑完即丢。

    StaticPool 让多条连接复用同一个内存库，否则每次连接都会拿到一个新的空库。
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
