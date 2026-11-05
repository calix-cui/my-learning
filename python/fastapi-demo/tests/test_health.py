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
    assert "/api/products" in paths
    assert "/api/products/{product_id}" in paths
    assert "/api/products/count" in paths
    assert "/api/categories" in paths
    assert "/api/categories/{category_id}" in paths
    assert "/api/categories/statistics" in paths
