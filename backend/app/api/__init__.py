from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(chat_router)
