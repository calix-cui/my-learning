import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.models import Category, Product
from app.schemas.category import CategoryCreateRequest

logger = logging.getLogger(__name__)

# 请求1：查询 “饮料” -> 饮料没有 -> 写进去 新增 "饮料"
# 请求2：查询 “饮料” -> 饮料没有 —> 新增 "饮料"（报错了）


def create_category(db: Session, payload: CategoryCreateRequest) -> Category:
    name = payload.name.strip()
    # 排除全空名称
    if not name:
        raise BusinessError("分类名称不能只包含空")

    # statement = select(Category.id).where(Category.name == name)
    # exsist_id = db.scalar(statement)
    # if exsist_id is not None:
    #     raise BusinessError("分类名称已存在", code=409)

    category = Category(name=name)

    try:
        db.add(category)
        db.commit()
        db.refresh(category)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("新增分类数据库操作失败")
        # 分类名有唯一约束，仅 MySQL 1062 表示这里的重名冲突。
        if isinstance(exc, IntegrityError) and exc.orig.args[0] == 1062:
            raise BusinessError("分类名称已存在", code=409) from exc
        raise
    return category


def get_categories(db: Session):
    """查询所有的商品分类"""
    try:
        statement = select(Category).order_by(Category.id.desc())
        return db.scalars(statement).all()
        # db.scalars(statement) 执行语句并取得其中的 ORM 对象，.all() 将全部对象取出

    except SQLAlchemyError as exc:
        logger.exception("查询分类列表失败")
        raise BusinessError("查询分类失败，请稍后重试", code=500) from exc


def update_category(db: Session, payload: CategoryCreateRequest, category_id: int) -> Category:
    category = db.get(Category, category_id)
    # 先确认资源存在，再校验入参：不存在的分类无论传什么都应回 404。
    if not category:
        raise BusinessError(message="分类不存在", code=404)

    # 改名和新增走同一套规则：先去掉首尾空白，再拒绝没有实际内容的名称。
    # 否则 PATCH 能把「   」原样存进库，与 POST 的行为不一致。
    name = payload.name.strip()
    if not name:
        raise BusinessError("分类名称不能只包含空")

    category.name = name
    try:
        db.commit()
        db.refresh(category)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("修改分类数据库操作失败")
        # 分类名有唯一约束，仅 MySQL 1062 表示这里的重名冲突。
        if isinstance(exc, IntegrityError) and exc.orig.args[0] == 1062:
            raise BusinessError("分类名称已存在", code=409) from exc
        raise
    return category


def delete_category(db: Session, category_id: int):
    category = db.get(Category, category_id)
    if category is None:
        raise BusinessError(message="分类不存在", code=404)
    # 按商品所属分类统计，不能把商品主键当成分类外键。
    product_count = db.scalar(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    )
    if product_count > 0:
        raise BusinessError(message="分类下有其他商品，不能删除分类", code=409)
    try:
        db.delete(category)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("删除分类数据库操作失败")
        raise


def get_category_statistics(db: Session):

    stmt = (
        select(Category.id, Category.name, func.count(Product.id).label("product_count"))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id, Category.name)
        .order_by(Category.id.asc())
    )
    #     stmt 是本次查询语句，按执行过程分为三步：
    # select(...) 查询分类 ID、名称和计数。func.count(Product.id).label("product_count") 计算非 NULL 的商品 ID 数量，并把结果列命名为 product_count。
    # .outerjoin(Product, Product.category_id == Category.id) 以分类为左表，关联商品的分类外键；.group_by(Category.id, Category.name) 把同一分类的商品归为一组，没有商品的分类也保留。
    # .order_by(Category.id.asc()) 按分类 ID 升序；db.execute(stmt).all() 执行语句，取回包含三项的完整行列表。
    rows = db.execute(stmt).all()

    return [
        {"id": category_id, "name": category_name, "product_count": product_count}
        for category_id, category_name, product_count in rows
    ]
