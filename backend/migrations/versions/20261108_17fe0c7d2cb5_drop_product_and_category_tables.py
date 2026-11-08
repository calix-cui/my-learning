"""drop product and category tables

商品与分类模块已归档到 archive/product-admin/，这里把对应两张表从库里移除。
downgrade 会按原结构重建（数据不恢复），结构与 2a89b3237f54 的 initial schema 一致。

Revision ID: 17fe0c7d2cb5
Revises: b1b54e93e0ca
Create Date: 2026-11-08 22:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17fe0c7d2cb5"
down_revision: str | Sequence[str] | None = "b1b54e93e0ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 先删有外键的子表，再删父表
    op.drop_table("products")
    op.drop_table("categories")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("name", sa.String(length=50), nullable=False, comment="分类名称"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        comment="商品分类表",
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("category_id", sa.Integer(), nullable=False, comment="所属分类ID"),
        sa.Column("name", sa.String(length=50), nullable=False, comment="商品名称"),
        sa.Column(
            "price", sa.Numeric(precision=8, scale=2), nullable=False, comment="商品单价（元）"
        ),
        sa.Column("stock", sa.Integer(), nullable=False, comment="库存数量"),
        sa.Column("shelf_status", sa.Boolean(), nullable=False, comment="是否上架"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="商品表",
    )
