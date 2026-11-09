"""账号相关的业务动作：注册、登录校验、会话创建/校验/撤销、改密。

约定（与项目其他 service 一致）：
- 入参是已经过 Pydantic 校验的数据，这里只做业务规则；
- 业务错误抛 `BusinessError(message, code)`，由全局处理器转成统一响应；
- 所有「按 id 找东西」的函数都要求传当前用户，越权一律返回 404 而不是 403。
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.tokens import hash_token, new_token
from app.common.exceptions import BusinessError
from app.config import settings
from app.models import LoginSession, User

# 每次请求都写一次 last_seen_time 没必要，超过这个间隔才刷新
LAST_SEEN_REFRESH = timedelta(hours=1)

# 会话列表里展示的设备信息不必太长
MAX_USER_AGENT = 255
MAX_IP = 64


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_password(raw_password: str) -> str:
    """长度是主要防线：8–72 位，不强制字符种类（NIST SP 800-63B 取向）。"""
    password = raw_password.strip("\n")
    if len(password) < 8:
        raise BusinessError("密码至少 8 位")
    if len(password) > 72:
        raise BusinessError("密码最多 72 位")
    return password


def register_user(db: Session, email: str, password: str, display_name: str | None = None) -> User:
    if not settings.allow_registration:
        raise BusinessError("注册已关闭", code=403)

    normalized = normalize_email(email)
    exists = db.scalar(select(User).where(User.email == normalized))
    if exists is not None:
        raise BusinessError("该邮箱已注册", code=409)

    user = User(
        email=normalized,
        password_hash=hash_password(_validate_password(password)),
        display_name=(display_name or "").strip() or None,
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    """校验邮箱密码。不管是「没有这个人」还是「密码不对」，对外都是同一句话。"""
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not verify_password(password, user.password_hash):
        raise BusinessError("邮箱或密码不正确", code=401)
    if not user.is_active:
        raise BusinessError("账号已被停用", code=403)

    # 哈希参数升级（当前为默认参数，通常不会触发）
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_time = datetime.now()
    db.commit()
    db.refresh(user)
    return user


def create_session(
    db: Session, user: User, user_agent: str | None = None, ip: str | None = None
) -> tuple[str, LoginSession]:
    """创建登录会话，返回（明文令牌, 会话行）。明文只交给 Cookie。"""
    token = new_token()
    now = datetime.now()
    session = LoginSession(
        user_id=user.id,
        token_hash=hash_token(token),
        user_agent=(user_agent or "")[:MAX_USER_AGENT] or None,
        ip=(ip or "")[:MAX_IP] or None,
        last_seen_time=now,
        expires_time=now + timedelta(days=settings.session_ttl_days),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


def resolve_session(db: Session, token: str) -> tuple[User, LoginSession] | None:
    """按令牌找到用户与会话。过期或停用的会话会被清掉并返回 None。"""
    if not token:
        return None

    row = db.execute(
        select(LoginSession, User)
        .join(User, User.id == LoginSession.user_id)
        .where(LoginSession.token_hash == hash_token(token))
    ).first()
    if row is None:
        return None

    session, user = row
    now = datetime.now()
    if session.expires_time <= now or not user.is_active:
        db.delete(session)
        db.commit()
        return None

    # 滑动续期：隔一段时间才写库，避免每个请求都产生一次 UPDATE
    if now - session.last_seen_time > LAST_SEEN_REFRESH:
        session.last_seen_time = now
        session.expires_time = now + timedelta(days=settings.session_ttl_days)
        db.commit()
    return user, session


def list_sessions(db: Session, user_id: int) -> list[LoginSession]:
    return list(
        db.scalars(
            select(LoginSession)
            .where(LoginSession.user_id == user_id)
            .order_by(LoginSession.last_seen_time.desc())
        ).all()
    )


def revoke_session(db: Session, user_id: int, session_id: int) -> None:
    session = db.scalar(
        select(LoginSession).where(LoginSession.id == session_id, LoginSession.user_id == user_id)
    )
    if session is None:
        # 别人的会话在这里和不存在是一个结果
        raise BusinessError("登录会话不存在", code=404)
    db.delete(session)
    db.commit()


def revoke_token(db: Session, token: str) -> None:
    """登出：令牌对应会话直接删除，重复登出不报错。"""
    if not token:
        return
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == hash_token(token)))
    if session is not None:
        db.delete(session)
        db.commit()


def revoke_other_sessions(db: Session, user_id: int, keep_session_id: int | None) -> None:
    """改密后踢掉其他设备，保留当前这台。"""
    sessions = db.scalars(select(LoginSession).where(LoginSession.user_id == user_id)).all()
    for session in sessions:
        if keep_session_id is not None and session.id == keep_session_id:
            continue
        db.delete(session)
    db.commit()


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise BusinessError("原密码不正确")
    new_password = _validate_password(new_password)
    user.password_hash = hash_password(new_password)
    db.commit()
