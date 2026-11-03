from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.database import Base

class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {"comment": "商品分类表"}

    name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="分类名称"
    )
