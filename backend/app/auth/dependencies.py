"""鉴权依赖：把「当前请求属于谁」变成一个可直接注入的对象。

两种凭证都支持，优先级 Bearer > Cookie：
1. `Authorization: Bearer <token>`：给脚本 / 将来的桌面端 / API Token 用；
2. Cookie `my_agent_session`：给浏览器用（HttpOnly，前端 JS 读不到）。
"""

from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth import service
from app.common.exceptions import BusinessError
from app.config import settings
from app.dependencies import get_db
from app.models import LoginSession, User

# 会话 Cookie 名。改这里要同步前端 client 与部署文档
SESSION_COOKIE = "my_agent_session"


def get_session_token(request: Request) -> str | None:
    """从 Bearer 或 Cookie 中取令牌，取不到返回 None。"""
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    return request.cookies.get(SESSION_COOKIE)


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    token = get_session_token(request)
    resolved = service.resolve_session(db, token) if token else None
    if resolved is None:
        raise BusinessError("请先登录", code=401)
    user, _session = resolved
    # 挂到 request.state，便于日志/审计读取，也避免重复解析
    request.state.user = user
    return user


def get_current_session(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> LoginSession:
    """需要知道「当前是哪台设备」时用（例如改密后保留当前会话）。"""
    token = get_session_token(request)
    resolved = service.resolve_session(db, token) if token else None
    if resolved is None:
        raise BusinessError("请先登录", code=401)
    _user, session = resolved
    request.state.user = _user
    return session


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSession = Annotated[LoginSession, Depends(get_current_session)]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        # 本地开发是 http，只有生产（https）才带 Secure，否则浏览器不会回传
        secure=settings.app_env == "production",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
