import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func, select

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


def get_products(
    db: Session,
    keyword: str | None = None,
    category_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
):
    keyword = (keyword or "").strip()
    filters = []
    # 有实际关键词时，才搜索名称
    if keyword:
        filters.append(Product.name.contains(keyword, autoescape=True))
        # 表示商品名称包含关键词
        # 它生成带参数的 LIKE 查询，autoescape=True 将关键词里的 %、_ 等字符按普通字符处理，输入 % 不会因此变成匹配全部名称
    # 只有提供分类 ID 时才筛选，不把未提供分类误解为查询某个默认分类
    if category_id is not None:
        filters.append(Product.category_id == category_id)
        # SQLAlchemy 的 ORM 属性重写了比较运算符 ==，使它返回 SQL 表达式对象，而不是普通布尔值。

    try:
        total_statement = select(func.count(Product.id)).where(*filters)
        # 统计语句只有一行一列，用 scalar() 取整数。scalars() 返回的是 ScalarResult 结果集对象，
        # 传给 ProductPageResponse.total（int 字段）会抛 ValidationError，接口直接 500。
        total = db.scalar(total_statement)

        statement = (
            select(Product)
            .where(*filters)
            .order_by(Product.id.desc())
            .offset(
                (page - 1) * page_size
            )  # page=1， page_size=10  第二页就从序号10开始查询   序号是从0开始计数的
            .limit(page_size)
        )
        items = db.scalars(statement).all()
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except SQLAlchemyError as exc:
        logger.exception("查询商品列表失败")
        raise BusinessError("查询商品列表失败，请稍后重试", code=500) from exc

# scalar() 和 scalars() 的区别也不是“数字”和“对象”：
# 它们都取每行的第一列，具体类型由 select() 选择的内容决定
# scalar() 只返回第一行的第一列，没有结果行时返回 None；
# scalars() 提供各行第一列的结果，再用 .all() 全部取出

def count_products(db: Session):
    try:
        statement = select(func.count(Product.id))
        return db.scalar(statement)
        # db.scalar() 取查询结果第一行的第一列，适合读取这个整数
    except SQLAlchemyError as exc:
        logger.exception("统计商品数量失败")
        raise BusinessError("统计商品数量失败，请稍后重试", code=500) from exc

def get_product(db: Session, product_id: int):
    try:
        return db.get(Product, product_id)
    except SQLAlchemyError as exc:
        logger.exception("查询商品详情失败")
        raise BusinessError("查询商品失败，请稍后重试", code=500) from exc
