# common 是本课程存放共用代码的包，不是 FastAPI 要求的固定目录。业务 schema 仍放在 schemas，通用响应与异常处理放在这个公共包。
from typing import Any

from pydantic import BaseModel


class Response(BaseModel):
    """API层统一返回的数据对象"""

    code: int
    message: str
    data: Any = None

    @classmethod
    # @classmethod 声明类方法，调用时写 Response.success(...)
    def success(cls, data: Any = None, message: str = "请求成功"):
        # cls 就是当前的 Response 类
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str, data: Any = None):
        return cls(code=code, message=message, data=data)
