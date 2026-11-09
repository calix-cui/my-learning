"""账号接口：注册、登录、登出、当前用户、设备列表、改密。

- 成功响应仍是 `{"code":200,"message":"请求成功","data":{...}}`；
- 登录态通过 HttpOnly Cookie `my_agent_session` 维持，前端 JS 读不到令牌；
- 未登录访问业务接口由 `Depends(get_current_user)` 统一拦成 401。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi import Response as FastapiResponse
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.dependencies import (
    SESSION_COOKIE,
    CurrentSession,
    CurrentUser,
    clear_session_cookie,
    set_session_cookie,
)
from app.common.response import Response
from app.dependencies import get_db
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    SessionListResponse,
    SessionResponse,
    UserDetailResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["账号相关的接口"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=Response, summary="注册并直接登录")
def register(
    request: Request,
    payload: RegisterRequest,
    response: FastapiResponse,
    db: DbSession,
):
    user = service.register_user(db, payload.email, payload.password, payload.display_name)
    token, _session = service.create_session(
        db, user, request.headers.get("user-agent"), request.client.host if request.client else None
    )
    set_session_cookie(response, token)
    return Response.success(data=UserDetailResponse.model_validate(user).model_dump(mode="json"))


@router.post("/login", response_model=Response, summary="登录")
def login(request: Request, payload: LoginRequest, response: FastapiResponse, db: DbSession):
    user = service.authenticate(db, payload.email, payload.password)
    token, _session = service.create_session(
        db, user, request.headers.get("user-agent"), request.client.host if request.client else None
    )
    set_session_cookie(response, token)
    return Response.success(data=UserDetailResponse.model_validate(user).model_dump(mode="json"))


@router.post("/logout", response_model=Response, summary="登出（幂等）")
def logout(request: Request, response: FastapiResponse, db: DbSession):
    token = request.cookies.get(SESSION_COOKIE)
    service.revoke_token(db, token or "")
    clear_session_cookie(response)
    return Response.success(message="已退出登录")


@router.get("/me", response_model=Response, summary="当前登录用户")
def read_me(user: CurrentUser):
    return Response.success(data=UserDetailResponse.model_validate(user).model_dump(mode="json"))


@router.get("/sessions", response_model=Response, summary="我的登录设备")
def read_sessions(user: CurrentUser, session: CurrentSession, db: DbSession):
    rows = service.list_sessions(db, user.id)
    items = [
        SessionResponse.model_validate(row)
        .model_copy(update={"is_current": row.id == session.id})
        .model_dump(mode="json")
        for row in rows
    ]
    return Response.success(data=SessionListResponse(items=items).model_dump(mode="json"))


@router.delete("/sessions/{session_id}", response_model=Response, summary="撤销某个登录设备")
def delete_session(session_id: int, user: CurrentUser, db: DbSession):
    service.revoke_session(db, user.id, session_id)
    return Response.success(message="已撤销该设备的登录")


@router.post("/password", response_model=Response, summary="修改密码并踢掉其他设备")
def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser,
    session: CurrentSession,
    db: DbSession,
):
    service.change_password(db, user, payload.old_password, payload.new_password)
    service.revoke_other_sessions(db, user.id, keep_session_id=session.id)
    return Response.success(message="密码已修改，其他设备已退出登录")


# 供测试与前端类型对齐使用
__all__ = ["router", "UserResponse"]
