from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from typing import Annotated

from app.dependencies import get_db
from app.common.response import Response
from app.schemas.category import CategoryCreateRequest, CategoryResponse, CategoryStatisticResponse
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["分类相关的接口"])


# @router.post("", response_model=Response)
# def create_category(payload: CategoryCreateRequest, db: Session = Depends(get_db)):
#     return Response.success(
#         data=CategoryResponse.model_validate(
#             category_service.create_category(db, payload)
#         )
#     )
@router.post(
    "",
    response_model=Response,
    summary="新增商品分类",
    description="接收分类名称，创建分类并返回分类信息；分类名称重复时返回409。",
)
def create_category(
    payload: CategoryCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    # db 不再设置 Python 默认值，由 FastAPI 通过依赖注入提供
):
    return Response.success(
        data=CategoryResponse.model_validate(
            category_service.create_category(db, payload)
        )
    )


@router.get(
    "",
    response_model=Response,
    summary="查询商品分类列表",
    description="按分类ID倒序返回所有分类；没有分类时，data为空列表。",
)
def read_categories(db: Annotated[Session, Depends(get_db)]):
    return Response.success(
        data=[
            CategoryResponse.model_validate(item)
            for item in category_service.get_categories(db)
            # 分类列表逐个用 CategoryResponse.model_validate() 转换 ORM 对象，再放入 Response.success(data=...)
        ]
    )


@router.patch(
    "/{category_id}",
    response_model=Response,
    summary="修改分类名称",
    description="按分类ID修改名称并返回分类信息；重名时返回409，不存在时返回404。",
)
def patch_category(
    payload: CategoryCreateRequest,
    category_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    # 分类对象通过响应模型处理，沿用已有字段和时间序列化规则。
    return Response.success(
        data=CategoryResponse.model_validate(
            category_service.update_category(
                db=db, payload=payload, category_id=category_id
            )
        )
    )

@router.delete(
    "/{category_id}",
    response_model=Response,
    summary="删除商品分类",
    description="仅删除没有商品的分类；有商品时返回409，不存在时返回404，成功返回统一成功响应。",
)
def delete_category(
    category_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    category_service.delete_category(db=db, category_id=category_id)
    return Response.success()

@router.get(
    "/statistics",
    response_model=Response,
    summary="统计分类商品数量",
    description="按分类ID升序返回分类ID、名称和商品数量；没有商品的分类也保留，数量为0。",
)
def read_category_statistics(db: Annotated[Session, Depends(get_db)]):
    return Response.success(
        data=[
            CategoryStatisticResponse.model_validate(item)
            for item in category_service.get_category_statistics(db=db)
        ]
    )
