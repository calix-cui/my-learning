from fastapi import APIRouter

from app.api.categories import router as category_router
from app.api.chat import router as chat_router
from app.api.products import router as product_router

router = APIRouter(prefix="/api")
router.include_router(category_router)
router.include_router(product_router)
router.include_router(chat_router)
