"""接口层校验测试：走完整的 FastAPI 请求链路，但都停在“进入数据库之前”。

- 参数校验失败 → 422，由 handle_validation_error 统一包装
- 名称全空白 → 400，由 service 的 strip 检查拦下（不产生 SQL）
因此这些用例不需要 MySQL，可在 CI 里直接跑。
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_product_missing_fields_returns_422():
    response = client.post("/api/products", json={"name": "只有名称"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 422
    assert body["message"] == "请求参数校验失败"
    locs = {tuple(item["loc"]) for item in body["data"]}
    assert ("body", "category_id") in locs
    assert ("body", "price") in locs


def test_create_product_invalid_price_returns_422():
    response = client.post(
        "/api/products",
        json={"category_id": 1, "name": "可口可乐", "price": "3.505"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


def test_create_product_blank_name_returns_400():
    # schema 的 min_length 只看长度，"   " 能通过；真正的空白判断在 service 层
    response = client.post(
        "/api/products",
        json={"category_id": 1, "name": "   ", "price": "3.50"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": 400,
        "message": "商品名称不能只包含空白",
        "data": None,
    }


def test_create_category_blank_name_returns_400():
    response = client.post("/api/categories", json={"name": "   "})

    assert response.status_code == 400
    assert response.json()["message"] == "分类名称不能只包含空"


def test_path_id_must_be_positive():
    response = client.get("/api/products/0")

    assert response.status_code == 422
    assert response.json()["code"] == 422


def test_unknown_path_returns_unified_404():
    response = client.get("/api/not-exists")

    assert response.status_code == 404
    assert response.json() == {"code": 404, "message": "Not Found", "data": None}
