from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
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
app.include_router(api_router)

app.add_exception_handler(BusinessError, handle_business_error)
app.add_exception_handler(SQLAlchemyError, handle_database_error)
app.add_exception_handler(StarletteHTTPException, handle_http_error)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.add_exception_handler(Exception, handle_unexpected_error)


@app.get("/")
def read_root():
    return {"message": "FastAPI服务正在运行中"}
