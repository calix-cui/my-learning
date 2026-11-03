from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"comment": "商品表"}

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False, comment="所属分类ID"
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="商品名称")
    price: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, comment="商品单价（元）"
    )
    stock: Mapped[int] = mapped_column(nullable=False, default=0, comment="库存数量")
    shelf_status: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否上架"
    )
