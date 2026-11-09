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
    "mysql+pymysql://test:test@127.0.0.1:3306/my_agent_test?charset=utf8mb4",
)

# 本地 .env 可能配了真实模型（LLM_PROVIDER=openai + 真 key）。测试固定走 fake：
# 既保证不联网、不花额度，也避免用例依赖开发者本机的 .env。
os.environ["LLM_PROVIDER"] = "fake"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  导入即把模型注册到 Base.metadata
from app.auth.service import register_user
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import User


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


def _override_get_db(db_session: Session):
    """把 get_db 换成同一个内存 SQLite 会话，接口层与服务层看到同一份数据。"""

    def override():
        yield db_session

    return override


@pytest.fixture()
def user(db_session: Session) -> User:
    """服务层测试默认用一个已注册用户；需要第二个用户时直接调用 register_user。"""
    return register_user(db_session, "user@example.com", "password123")


@pytest.fixture()
def anon_client(db_session: Session) -> Iterator[TestClient]:
    """未登录客户端：所有业务接口都应 401。"""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """已登录客户端：真实走一遍注册接口，拿到 HttpOnly Cookie 后再做业务请求。"""
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        assert response.status_code == 200, response.text
        yield test_client
    finally:
        app.dependency_overrides.clear()
