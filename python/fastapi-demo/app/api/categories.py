from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.common.response import Response
from app.schemas.category import CategoryCreateRequest, CategoryResponse
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["分类相关的接口"])


@router.post("", response_model=Response)
def create_category(payload: CategoryCreateRequest, db: Session = Depends(get_db)):
    return Response.success(
        data=CategoryResponse.model_validate(
            category_service.create_category(db, payload)
        )
    )
