import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.models import Category
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

