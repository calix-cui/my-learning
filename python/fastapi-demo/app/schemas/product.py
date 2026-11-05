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

class ProductWithCategoryNameResponse(ProductResponse):
    """复用商品响应字段，只增加所属分类名称。"""

    category_name: str = Field(description="分类名称")

class ProductPageResponse(BaseModel):
    items: list[ProductWithCategoryNameResponse] = Field(description="当前页商品")
    total: int = Field(description="符合条件的商品总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")

class ProductUpdateRequest(BaseModel):
    """修改商品，客户端可以提交的字段，局部修改"""

    model_config = ConfigDict(str_strip_whitespace=True)
    # ConfigDict(str_strip_whitespace=True) 会在模型校验时去掉字符串首尾空白

    category_id: int | None = Field(
        default=None, gt=0, description="商品分类的ID，必须是正整数"
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="商品名称，不超过50个字符",
    )
    price: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
        max_digits=8,
        description="商品价格，最大保留2位小数",
    )
    stock: int | None = Field(default=None, ge=0, description="库存，不小于0")
    shelf_status: bool | None = Field(default=None, description="上架状态")
