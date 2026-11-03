import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.models import Category, Product
from app.schemas.product import ProductCreateRequest

logger = logging.getLogger(__name__)


def create_product(db: Session, payload: ProductCreateRequest) -> Product:
    name = payload.name.strip()
    # 先去掉首尾空白，再拒绝没有实际内容的商品名称。
    if not name:
        raise BusinessError("商品名称不能只包含空白")

    try:
        category = db.get(Category, payload.category_id)
        # 正整数分类 ID 仍可能不存在，确认分类后才允许新增商品。
        if category is None:
            raise BusinessError("商品分类不存在")

        # **{"name": "可口可乐"} -> name="可口可乐", stock=100
        product = Product(**payload.model_dump())
        product.name = name
        db.add(product)
        db.commit()
        db.refresh(product)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("新增商品数据库操作失败")
        raise

    return product
