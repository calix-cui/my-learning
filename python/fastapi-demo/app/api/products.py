from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.common.response import Response
from app.schemas.product import ProductCreateRequest, ProductResponse
from app.services import product_service

router = APIRouter(prefix="/products", tags=["商品相关的接口"])


# model -> schema -> service -> api
@router.post("", response_model=Response)
def create_product(payload: ProductCreateRequest, db: Session = Depends(get_db)):
    return Response.success(
        data=ProductResponse.model_validate(product_service.create_product(db, payload))
    )
