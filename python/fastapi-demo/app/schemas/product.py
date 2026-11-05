from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProductCreateRequest(BaseModel):
    category_id: int = Field(gt=0, description="所属分类ID")
    name: str = Field(min_length=1, max_length=50, description="商品名称")
    price: Decimal = Field(
        ge=0, decimal_places=2, max_digits=8, description="商品单价（元）"
    )
    stock: int = Field(default=0, ge=0, description="库存数量")
    shelf_status: bool = Field(default=True, description="是否上架")


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="商品ID")
    category_id: int = Field(description="所属分类ID")
    name: str = Field(description="商品名称")
    price: Decimal = Field(description="商品单价（元）")
    stock: int = Field(description="库存数量")
    shelf_status: bool = Field(description="是否上架")
    create_time: datetime = Field(description="创建时间")

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> str:
        return f"{value:.2f}"

    @field_serializer("create_time")
    def serialize_create_time(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

class ProductCountResponse(BaseModel):
    total: int = Field(description="全部商品数量")

class ProductPageResponse(BaseModel):
    items: list[ProductResponse] = Field(description="当前页商品")
    total: int = Field(description="符合条件的商品总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
