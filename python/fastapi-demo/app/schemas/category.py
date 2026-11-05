from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class CategoryCreateRequest(BaseModel):
    # CategoryCreateRequest 说明客户端能提交什么
    name: str = Field(min_length=1, max_length=50, description="分类名称")


class CategoryResponse(BaseModel):
    # CategoryResponse 说明接口返回什么
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="分类ID")
    name: str = Field(description="分类名称")
    create_time: datetime = Field(description="创建时间")

    @field_serializer("create_time")
    def serialize_create_time(self, value: datetime) -> str:
        # 2026-10-22 16:05:10
        return value.strftime("%Y-%m-%d %H:%M:%S")

class CategoryStatisticResponse(BaseModel):
    """分类商品数量统计，包含没有商品的分类"""

    id: int = Field(description="分类ID")
    name: str = Field(description="分类名称")
    product_count: int = Field(description="该分类下的商品数量")
