"""商品管理网站的演示数据种子脚本。

用途：为「简易商品管理网站」准备一批可直接演示的分类与商品数据，
      前端联调、截图验收时不必手动一条条录入。

幂等：按名称判断是否已存在，已存在的分类/商品直接跳过（不修改、不重复插入），
      因此可以反复执行，不会产生重复数据。

运行：./.venv/bin/python -m app.seed
      依赖 .env 中的 DATABASE_URL，需要 MySQL 已启动且表已建好（make init-db）。
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessError
from app.database import SessionLocal
from app.models import Category, Product
from app.schemas.category import CategoryCreateRequest
from app.schemas.product import ProductCreateRequest
from app.services import category_service, product_service

logger = logging.getLogger(__name__)

# 演示分类：按这里的顺序创建，名称与前端下拉、统计口径保持一致。
SEED_CATEGORY_NAMES = ("饮料", "零食", "乳品")

# 演示商品：共 12 个，每个分类 4 个，便于演示分页（page_size=5/10 时有多页）；
# 其中 2 个下架（奥利奥饼干、光明酸奶），用于演示列表里的状态标签。
# 价格用字符串书写、再转 Decimal，避免 3.5 这类二进制浮点误差写进数据库。
SEED_PRODUCTS = (
    {
        "category_name": "饮料",
        "name": "可口可乐",
        "price": "3.50",
        "stock": 120,
        "shelf_status": True,
    },
    {"category_name": "饮料", "name": "雪碧", "price": "3.00", "stock": 80, "shelf_status": True},
    {
        "category_name": "饮料",
        "name": "农夫山泉",
        "price": "2.00",
        "stock": 200,
        "shelf_status": True,
    },
    {
        "category_name": "饮料",
        "name": "东方树叶",
        "price": "5.50",
        "stock": 35,
        "shelf_status": True,
    },
    {
        "category_name": "零食",
        "name": "乐事薯片",
        "price": "6.50",
        "stock": 60,
        "shelf_status": True,
    },
    {
        "category_name": "零食",
        "name": "奥利奥饼干",
        "price": "9.90",
        "stock": 0,
        "shelf_status": False,
    },
    {
        "category_name": "零食",
        "name": "旺旺雪饼",
        "price": "5.80",
        "stock": 45,
        "shelf_status": True,
    },
    {
        "category_name": "零食",
        "name": "三只松鼠坚果",
        "price": "28.80",
        "stock": 12,
        "shelf_status": True,
    },
    {
        "category_name": "乳品",
        "name": "蒙牛纯牛奶",
        "price": "4.50",
        "stock": 90,
        "shelf_status": True,
    },
    {
        "category_name": "乳品",
        "name": "光明酸奶",
        "price": "3.80",
        "stock": 0,
        "shelf_status": False,
    },
    {
        "category_name": "乳品",
        "name": "伊利安慕希",
        "price": "7.50",
        "stock": 66,
        "shelf_status": True,
    },
    {"category_name": "乳品", "name": "特仑苏", "price": "6.80", "stock": 30, "shelf_status": True},
)


def _find_category(db: Session, name: str) -> Category | None:
    """按名称查询分类，存在则返回分类对象，否则返回 None。"""
    return db.scalar(select(Category).where(Category.name == name))


def _find_product(db: Session, name: str) -> Product | None:
    """按名称查询商品，存在则返回商品对象，否则返回 None。"""
    return db.scalar(select(Product).where(Product.name == name))


def seed_categories(db: Session) -> tuple[dict[str, int], int]:
    """确保演示分类存在，返回「分类名 -> 分类ID」映射与本次新增数量。"""
    category_ids: dict[str, int] = {}
    added = 0
    for name in SEED_CATEGORY_NAMES:
        existing = _find_category(db, name)
        if existing is not None:
            print(f"跳过已存在的分类：{name}（id={existing.id}）")
            category_ids[name] = existing.id
            continue
        # 走 service 层：名称去空白、提交、唯一约束冲突转 409 等逻辑都复用接口那一套。
        category = category_service.create_category(db, CategoryCreateRequest(name=name))
        print(f"新增分类：{name}（id={category.id}）")
        category_ids[name] = category.id
        added += 1
    return category_ids, added


def seed_products(db: Session, category_ids: dict[str, int]) -> tuple[int, int]:
    """确保演示商品存在，返回（本次新增数量，跳过数量）。"""
    added = 0
    skipped = 0
    for item in SEED_PRODUCTS:
        name = item["name"]
        if _find_product(db, name) is not None:
            print(f"跳过已存在的商品：{name}")
            skipped += 1
            continue
        payload = ProductCreateRequest(
            category_id=category_ids[item["category_name"]],
            name=name,
            price=Decimal(item["price"]),
            stock=item["stock"],
            shelf_status=item["shelf_status"],
        )
        # 走 service 层：校验分类存在、统一提交与失败回滚，和真实接口行为保持一致。
        product = product_service.create_product(db, payload)
        print(f"新增商品：{name}（id={product.id}，价格 ¥{product.price:.2f}）")
        added += 1
    return added, skipped


def main() -> int:
    """执行种子数据写入，返回进程退出码（0 成功，1 失败）。"""
    print("开始写入商品管理演示数据……")
    try:
        with SessionLocal() as db:
            category_ids, category_added = seed_categories(db)
            product_added, product_skipped = seed_products(db, category_ids)
            # 结束后打印当前总量，方便确认前后端看到的数据规模。
            category_total = len(category_service.get_categories(db))
            product_total = product_service.count_products(db)
    except BusinessError as exc:
        print(f"种子数据写入失败：{exc}")
        return 1
    except SQLAlchemyError:
        logger.exception("种子数据写入时数据库操作失败")
        print("种子数据写入失败：数据库操作异常，请确认 MySQL 已启动且 .env 的 DATABASE_URL 正确。")
        return 1

    print("")
    print(
        f"完成：新增分类 {category_added} 个，新增商品 {product_added} 个，"
        f"跳过已存在商品 {product_skipped} 个。"
    )
    print(f"当前数据库共 {category_total} 个分类、{product_total} 个商品。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
