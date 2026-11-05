from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import router as api_router
from app.common.exceptions import (
    BusinessError,
    handle_business_error,
    handle_database_error,
    handle_http_error,
    handle_unexpected_error,
    handle_validation_error,
)
from app.common.response import Response

app = FastAPI(responses={422: {"model": Response, "description": "请求参数校验失败"}})

# 允许跨域的前端来源：Vite 开发服务器（5173）与 Vite 预览服务器（4173），
# localhost 与 127.0.0.1 两种写法都列出，避免前端用哪个地址访问都能连上后端。
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
# 开发期前端需要跨域直连后端，由 CORSMiddleware 在响应里补上 CORS 头；
# 生产环境应把 ALLOWED_ORIGINS 收窄成真实部署域名，不要保留本地调试地址。
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

app.add_exception_handler(BusinessError, handle_business_error)
app.add_exception_handler(SQLAlchemyError, handle_database_error)
app.add_exception_handler(StarletteHTTPException, handle_http_error)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.add_exception_handler(Exception, handle_unexpected_error)


@app.get("/")
def read_root():
    return {"message": "FastAPI服务正在运行中"}
