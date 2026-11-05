from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from typing import Annotated

from app.dependencies import get_db
from app.common.response import Response
from app.schemas.category import CategoryCreateRequest, CategoryResponse
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
    description="接收分类名称，创建分类并返回分类信息；分类名称重复时返回409。"
)
def create_category(
    payload: CategoryCreateRequest,
    db: Annotated[Session, Depends(get_db)]
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
    description="按分类ID倒序返回所有分类；没有分类时，data为空列表。"
)
def read_categories(db: Annotated[Session, Depends(get_db)]):
    return Response.success(
        data=[
            CategoryResponse.model_validate(item) for item in category_service.get_categories(db)
            # 分类列表逐个用 CategoryResponse.model_validate() 转换 ORM 对象，再放入 Response.success(data=...)
        ]
    )
