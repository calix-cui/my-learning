"""数据契约（Pydantic 模型）测试：把校验规则与序列化格式固定下来。

这一层不需要数据库，是回归成本最低的一层：接口字段一旦被改坏，这里先失败。
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.category import CategoryCreateRequest, CategoryResponse
from app.schemas.product import (
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
)


def test_product_create_accepts_valid_payload():
    payload = ProductCreateRequest(
        category_id=1, name="可口可乐", price="3.50", stock=10, shelf_status=True
    )

    assert payload.price == Decimal("3.50")
    assert payload.stock == 10


@pytest.mark.parametrize(
    "field, value",
    [
        ("price", "3.505"),  # 保留 3 位小数，超出 decimal_places=2
        ("price", "-1"),  # 价格不能为负
        ("stock", -1),  # 库存不能为负
        ("category_id", 0),  # 分类 ID 必须是正整数
        ("name", ""),  # 名称不能为空串
    ],
)
def test_product_create_rejects_invalid_field(field, value):
    payload = {
        "category_id": 1,
        "name": "可口可乐",
        "price": "3.50",
        "stock": 10,
        "shelf_status": True,
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        ProductCreateRequest(**payload)


def test_product_update_allows_partial_payload():
    # 局部修改：一个字段都不传是合法的，由 service 判断“没有可修改内容”
    assert ProductUpdateRequest().model_dump(exclude_unset=True) == {}
    assert ProductUpdateRequest(stock=5).model_dump(exclude_unset=True) == {"stock": 5}


def test_product_response_serializes_price_and_time():
    row = SimpleNamespace(
        id=1,
        category_id=2,
        name="可口可乐",
        price=Decimal("3.5"),
        stock=10,
        shelf_status=True,
        create_time=datetime(2026, 10, 22, 16, 5, 10),
    )

    data = ProductResponse.model_validate(row).model_dump()

    # 价格固定两位小数、时间固定格式，避免前端拿到 3.5 / ISO 字符串
    assert data["price"] == "3.50"
    assert data["create_time"] == "2026-10-22 16:05:10"


def test_category_request_trims_only_in_service_layer():
    # 这里只验证契约：长度按原始字符串算，全空白串通过模型校验，
    # 由 service 的 strip 逻辑拒绝（见 tests/test_api_validation.py）
    assert CategoryCreateRequest(name="   ").name == "   "
    with pytest.raises(ValidationError):
        CategoryCreateRequest(name="")


def test_category_response_serializes_create_time():
    row = SimpleNamespace(id=3, name="饮料", create_time=datetime(2026, 10, 22, 16, 5, 10))

    data = CategoryResponse.model_validate(row).model_dump()

    assert data == {"id": 3, "name": "饮料", "create_time": "2026-10-22 16:05:10"}
