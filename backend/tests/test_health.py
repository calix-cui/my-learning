"""应用能否正常装配的冒烟测试：不依赖数据库，可在 CI 中运行。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_running_message():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "FastAPI服务正在运行中"}


def test_openapi_exposes_business_routes():
    # 生成 OpenAPI 能发现路由注册、依赖声明、响应模型层面的错误
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    # 商品 / 分类接口已随商品管理模块归档（archive/product-admin/），现在只剩对话
    assert "/api/conversations" in paths
    assert "/api/conversations/{conversation_id}" in paths
    assert "/api/conversations/{conversation_id}/messages" in paths
    assert "/api/conversations/{conversation_id}/messages/stream" in paths


def test_healthz_is_independent_of_database():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_unavailable_when_database_is_down():
    # 占位连接串指向不存在的库/账号，就绪探针必须转成 503 而不是抛 500
    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "down"}
