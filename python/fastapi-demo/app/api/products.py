from typing import Annotated

# 使用 Annotated 可以将类型声明与依赖配置分离，并将常用依赖封装成可复用的类型别名，减少重复代码，让代码结构更清晰、易维护。

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.common.response import Response
from app.schemas.product import (
    ProductCreateRequest,
    ProductResponse,
    ProductPageResponse,
    ProductCountResponse,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["商品相关的接口"])


# model -> schema -> service -> api
@router.post(
    "",
    response_model=Response,
    summary="新增商品",
    description="接收商品资料，校验所属分类存在后创建商品，并返回生成的ID、创建时间等完整信息。",
)
def create_product(
    payload: ProductCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    # db: Session = Depends(get_db)
):
    return Response.success(
        data=ProductResponse.model_validate(product_service.create_product(db, payload))
    )


@router.get(
    "",
    response_model=Response,
    summary="分页模糊查询商品数据",
    description="支持按名称关键词和分类ID组合筛选，按商品ID倒序分页，返回当前页商品与筛选后的商品总数",
)
def get_page_products(
    db: Annotated[Session, Depends(get_db)],
    keyword: Annotated[
        str | None, Query(max_length=50, description="名称关键词")
    ] = None,
    category_id: Annotated[int | None, Query(gt=0, description="分类ID")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 10,
):
    """分页模糊查询商品数据"""
    page_data = product_service.get_products(
        db=db, keyword=keyword, category_id=category_id, page=page, page_size=page_size
    )
    return Response.success(data=ProductPageResponse.model_validate(page_data))


@router.get(
    "/count",
    response_model=Response,
    summary="统计商品总数",
    description="统计全部商品数量，不应用商品列表接口的关键词和分类筛选条件。",
)
def read_product_count(db: Annotated[Session, Depends(get_db)]):
    return Response.success(
        data=ProductCountResponse(total=product_service.count_products(db))
    )


@router.get(
    "/{product_id}",
    response_model=Response,
    summary="查询商品详情",
    description="根据正整数商品ID查询商品详情；商品不存在时返回404。",
)
def read_product(
    product_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    product = product_service.get_product(db, product_id)
    # 合法的正整数不一定有对应记录，没有商品时返回404而不是200和null。
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return Response.success(data=ProductResponse.model_validate(product))
