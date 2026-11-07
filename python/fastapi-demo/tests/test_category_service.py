"""分类服务层测试：用内存 SQLite 覆盖增删改查、唯一性与删除保护。"""

import pytest
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.schemas.category import CategoryCreateRequest
from app.services import category_service


def _create(db: Session, name: str):
    return category_service.create_category(db, CategoryCreateRequest(name=name))


def test_create_category_strips_surrounding_spaces(db_session: Session):
    category = _create(db_session, "  饮料  ")

    assert category.name == "饮料"
    assert category.id > 0


def test_create_category_rejects_blank_name(db_session: Session):
    with pytest.raises(BusinessError) as exc_info:
        _create(db_session, "   ")

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "分类名称不能只包含空"


def test_get_categories_returns_newest_first(db_session: Session):
    _create(db_session, "饮料")
    _create(db_session, "零食")

    names = [category.name for category in category_service.get_categories(db_session)]

    assert names == ["零食", "饮料"]


def test_update_category_renames_category(db_session: Session):
    category = _create(db_session, "饮料")

    updated = category_service.update_category(
        db_session, CategoryCreateRequest(name="酒水"), category.id
    )

    assert updated.id == category.id
    assert updated.name == "酒水"


def test_update_category_trims_surrounding_spaces(db_session: Session):
    category = _create(db_session, "饮料")

    updated = category_service.update_category(
        db_session, CategoryCreateRequest(name="  酒水  "), category.id
    )

    assert updated.name == "酒水"


def test_update_category_rejects_blank_name(db_session: Session):
    category = _create(db_session, "饮料")

    with pytest.raises(BusinessError) as exc_info:
        category_service.update_category(db_session, CategoryCreateRequest(name="   "), category.id)

    assert exc_info.value.code == 400
    assert str(exc_info.value) == "分类名称不能只包含空"
    # 失败后库里仍是原名，没有被写成空白
    db_session.refresh(category)
    assert category.name == "饮料"


def test_update_missing_category_raises_404(db_session: Session):
    with pytest.raises(BusinessError) as exc_info:
        category_service.update_category(db_session, CategoryCreateRequest(name="酒水"), 999)

    assert exc_info.value.code == 404
    assert str(exc_info.value) == "分类不存在"


def test_update_missing_category_prefers_404_over_blank_name(db_session: Session):
    # 资源不存在时先回 404，不能被入参校验抢在前面变成 400
    with pytest.raises(BusinessError) as exc_info:
        category_service.update_category(db_session, CategoryCreateRequest(name="   "), 999)

    assert exc_info.value.code == 404


def test_delete_category_with_products_is_blocked(db_session: Session):
    from app.schemas.product import ProductCreateRequest
    from app.services import product_service

    category = _create(db_session, "饮料")
    product_service.create_product(
        db_session,
        ProductCreateRequest(category_id=category.id, name="矿泉水", price="2.00", stock=10),
    )

    with pytest.raises(BusinessError) as exc_info:
        category_service.delete_category(db_session, category.id)

    assert exc_info.value.code == 409
    assert str(exc_info.value) == "分类下有其他商品，不能删除分类"


def test_delete_empty_category_succeeds(db_session: Session):
    category = _create(db_session, "临时分类")

    category_service.delete_category(db_session, category.id)

    assert category_service.get_categories(db_session) == []


def test_delete_missing_category_raises_404(db_session: Session):
    with pytest.raises(BusinessError) as exc_info:
        category_service.delete_category(db_session, 999)

    assert exc_info.value.code == 404


def test_statistics_include_empty_category(db_session: Session):
    from app.schemas.product import ProductCreateRequest
    from app.services import product_service

    drinks = _create(db_session, "饮料")
    _create(db_session, "空分类")
    product_service.create_product(
        db_session,
        ProductCreateRequest(category_id=drinks.id, name="矿泉水", price="2.00", stock=5),
    )

    stats = category_service.get_category_statistics(db_session)

    assert [row["name"] for row in stats] == ["饮料", "空分类"]
    assert [row["product_count"] for row in stats] == [1, 0]
