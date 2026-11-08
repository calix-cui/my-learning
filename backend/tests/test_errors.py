"""统一响应与业务异常测试：固定对外 JSON 契约。"""

from app.common.exceptions import BusinessError
from app.common.response import Response


def test_success_default_shape():
    body = Response.success().model_dump()

    assert body == {"code": 200, "message": "请求成功", "data": None}


def test_success_with_data_and_message():
    body = Response.success(data={"id": 1}, message="已创建").model_dump()

    assert body == {"code": 200, "message": "已创建", "data": {"id": 1}}


def test_error_keeps_business_code():
    body = Response.error(code=409, message="分类名称已存在").model_dump()

    assert body == {"code": 409, "message": "分类名称已存在", "data": None}


def test_business_error_defaults_to_400():
    exc = BusinessError("商品分类不存在")

    assert exc.code == 400
    assert str(exc) == "商品分类不存在"


def test_business_error_accepts_custom_code():
    exc = BusinessError("分类名称已存在", code=409)

    assert exc.code == 409
