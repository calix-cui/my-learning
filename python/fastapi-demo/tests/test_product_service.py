"""商品服务层测试：用内存 SQLite 覆盖新增校验、分页筛选、局部更新与删除。"""

import pytest
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.schemas.category import CategoryCreateRequest
from app.schemas.product import ProductCreateRequest, ProductUpdateRequest
from app.services import category_service, product_service


@pytest.fixture()
def category(db_session: Session):
    return category_service.create_category(db_session, CategoryCreateRequest(name="饮料"))


def _create(db: Session, category_id: int, name: str = "可乐", stock: int = 10):
    return product_service.create_product(
        db,
        ProductCreateRequest(category_id=category_id, name=name, price="3.50", stock=stock),
    )


def test_create_product_trims_name(db_session: Session, category):
    product = _create(db_session, category.id, name="  可乐  ")

    assert product.name == "可乐"
    assert product.price == pytest.approx(3.50)


def test_create_product_rejects_blank_name(db_session: Session, category):
    with pytest.raises(BusinessError) as exc_info:
        _create(db_session, category.id, name="   ")

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "商品名称不能只包含空白"


def test_create_product_with_missing_category_raises_400(db_session: Session):
    with pytest.raises(BusinessError) as exc_info:
        _create(db_session, 999)

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "商品分类不存在"


def test_get_products_paginates_and_counts(db_session: Session, category):
    for index in range(5):
        _create(db_session, category.id, name=f"商品{index}")

    first_page = product_service.get_products(db_session, page=1, page_size=2)
    second_page = product_service.get_products(db_session, page=2, page_size=2)
    last_page = product_service.get_products(db_session, page=3, page_size=2)

    assert first_page["total"] == 5
    assert [item["name"] for item in first_page["items"]] == ["商品4", "商品3"]
    assert [item["name"] for item in second_page["items"]] == ["商品2", "商品1"]
    assert [item["name"] for item in last_page["items"]] == ["商品0"]
    assert first_page["items"][0]["category_name"] == "饮料"


def test_get_products_filters_by_keyword(db_session: Session, category):
    _create(db_session, category.id, name="矿泉水")
    _create(db_session, category.id, name="可乐")

    result = product_service.get_products(db_session, keyword="矿泉")

    assert result["total"] == 1
    assert result["items"][0]["name"] == "矿泉水"


def test_get_products_keyword_treats_wildcard_literally(db_session: Session, category):
    _create(db_session, category.id, name="矿泉水")

    result = product_service.get_products(db_session, keyword="%")

    assert result["total"] == 0


def test_get_products_filters_by_category(db_session: Session):
    drinks = category_service.create_category(db_session, CategoryCreateRequest(name="饮料"))
    snacks = category_service.create_category(db_session, CategoryCreateRequest(name="零食"))
    _create(db_session, drinks.id, name="可乐")
    _create(db_session, snacks.id, name="乐事薯片")

    result = product_service.get_products(db_session, category_id=snacks.id)

    assert result["total"] == 1
    assert result["items"][0]["name"] == "乐事薯片"


def test_count_products(db_session: Session, category):
    _create(db_session, category.id, name="可乐")
    _create(db_session, category.id, name="雪碧")

    assert product_service.count_products(db_session) == 2


def test_get_product_returns_none_when_missing(db_session: Session):
    assert product_service.get_product(db_session, 999) is None


def test_update_product_applies_partial_changes(db_session: Session, category):
    product = _create(db_session, category.id, name="可乐")

    updated = product_service.update_product(db_session, ProductUpdateRequest(stock=99), product.id)

    assert updated.stock == 99
    assert updated.name == "可乐"


def test_update_product_trims_name(db_session: Session, category):
    product = _create(db_session, category.id, name="可乐")

    updated = product_service.update_product(
        db_session, ProductUpdateRequest(name="  雪碧  "), product.id
    )

    assert updated.name == "雪碧"


def test_update_product_rejects_blank_name(db_session: Session, category):
    product = _create(db_session, category.id, name="可乐")

    with pytest.raises(BusinessError) as exc_info:
        product_service.update_product(db_session, ProductUpdateRequest(name="   "), product.id)

    # 与新增商品同一个业务错误，而不是 Pydantic 的 422
    assert exc_info.value.code == 400
    assert str(exc_info.value) == "商品名称不能只包含空白"
    db_session.refresh(product)
    assert product.name == "可乐"


def test_update_product_without_fields_raises_400(db_session: Session, category):
    product = _create(db_session, category.id, name="可乐")

    with pytest.raises(BusinessError) as exc_info:
        product_service.update_product(db_session, ProductUpdateRequest(), product.id)

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "至少提交一个需要修改的字段"


def test_update_product_rejects_null_value(db_session: Session, category):
    product = _create(db_session, category.id, name="可乐")

    with pytest.raises(BusinessError) as exc_info:
        product_service.update_product(db_session, ProductUpdateRequest(stock=None), product.id)

    assert exc_info.value.code == 400
    assert "不允许为 null" in str(exc_info.value)


def test_update_missing_product_raises_404(db_session: Session):
    with pytest.raises(BusinessError) as exc_info:
        product_service.update_product(db_session, ProductUpdateRequest(stock=1), 999)

    assert exc_info.value.code == 404
    assert str(exc_info.value) == "未找到商品"


def test_update_product_rejects_unknown_category(db_session: Session, category):
    product = _create(db_session, category.id, name="可乐")

    with pytest.raises(BusinessError) as exc_info:
        product_service.update_product(
            db_session, ProductUpdateRequest(category_id=999), product.id
        )

    assert str(exc_info.value) == "商品分类不存在"


def test_delete_product(db_session: Session, category):
    product = _create(db_session, category.id, name="可乐")

    product_service.delete_product(db_session, product.id)

    assert product_service.get_product(db_session, product.id) is None


def test_delete_missing_product_raises_404(db_session: Session):
    with pytest.raises(BusinessError) as exc_info:
        product_service.delete_product(db_session, 999)

    assert exc_info.value.code == 404
    assert str(exc_info.value) == "商品不存在"
