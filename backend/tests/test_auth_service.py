"""账号模块的单元测试：密码、令牌、注册/登录/会话/改密。

用内存 SQLite（conftest 的 `db_session` 夹具），不依赖真实 MySQL。
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.tokens import hash_token, new_token
from app.common.exceptions import BusinessError
from app.config import settings
from app.models import LoginSession, User


def _make_user(db: Session, email: str = "a@example.com", password: str = "password123") -> User:
    return service.register_user(db, email, password)


# --- 密码与令牌 ---


def test_hash_password_is_argon2id_and_verifies():
    hashed = hash_password("password123")
    assert hashed.startswith("$argon2id$")
    assert verify_password("password123", hashed) is True
    assert verify_password("wrong-password", hashed) is False
    assert needs_rehash(hashed) is False


def test_verify_password_with_broken_hash_returns_false():
    assert verify_password("password123", "not-a-hash") is False


def test_token_is_random_and_hash_is_stable():
    first = new_token()
    second = new_token()
    assert first != second
    assert len(first) >= 40
    assert hash_token(first) == hash_token(first)
    assert len(hash_token(first)) == 64


# --- 注册 ---


def test_register_normalizes_email_and_sets_defaults(db_session: Session):
    user = service.register_user(db_session, "  Alice@Example.COM  ", "password123", " Alice ")
    assert user.email == "alice@example.com"
    assert user.display_name == "Alice"
    assert user.role == "user"
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2id$")


def test_register_rejects_duplicate_email(db_session: Session):
    _make_user(db_session)
    with pytest.raises(BusinessError) as exc_info:
        service.register_user(db_session, "A@example.com", "password123")
    assert exc_info.value.code == 409
    assert str(exc_info.value) == "该邮箱已注册"


@pytest.mark.parametrize("password", ["short", "1234567", ""])
def test_register_rejects_short_password(db_session: Session, password: str):
    with pytest.raises(BusinessError) as exc_info:
        service.register_user(db_session, "b@example.com", password)
    assert str(exc_info.value) == "密码至少 8 位"


def test_register_rejects_too_long_password(db_session: Session):
    with pytest.raises(BusinessError) as exc_info:
        service.register_user(db_session, "b@example.com", "x" * 73)
    assert str(exc_info.value) == "密码最多 72 位"


def test_register_respects_allow_registration_switch(db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "allow_registration", False)
    with pytest.raises(BusinessError) as exc_info:
        service.register_user(db_session, "c@example.com", "password123")
    assert exc_info.value.code == 403
    assert str(exc_info.value) == "注册已关闭"


# --- 登录 ---


def test_authenticate_updates_last_login(db_session: Session):
    _make_user(db_session)
    assert db_session.query(User).one().last_login_time is None

    user = service.authenticate(db_session, "A@EXAMPLE.com", "password123")
    assert user.last_login_time is not None


@pytest.mark.parametrize(
    ("email", "password"),
    [("a@example.com", "wrong-password"), ("nobody@example.com", "password123")],
)
def test_authenticate_hides_which_part_is_wrong(db_session: Session, email: str, password: str):
    _make_user(db_session)
    with pytest.raises(BusinessError) as exc_info:
        service.authenticate(db_session, email, password)
    assert exc_info.value.code == 401
    assert str(exc_info.value) == "邮箱或密码不正确"


def test_authenticate_rejects_inactive_account(db_session: Session):
    user = _make_user(db_session)
    user.is_active = False
    db_session.commit()

    with pytest.raises(BusinessError) as exc_info:
        service.authenticate(db_session, "a@example.com", "password123")
    assert exc_info.value.code == 403
    assert str(exc_info.value) == "账号已被停用"


# --- 会话 ---


def test_create_session_stores_only_hash(db_session: Session):
    user = _make_user(db_session)
    token, session = service.create_session(db_session, user, "pytest-agent", "127.0.0.1")

    assert session.token_hash == hash_token(token)
    assert token not in (session.token_hash,)
    assert session.expires_time > datetime.now()
    assert session.user_agent == "pytest-agent"
    assert session.ip == "127.0.0.1"


def test_resolve_session_returns_user(db_session: Session):
    user = _make_user(db_session)
    token, session = service.create_session(db_session, user)
    resolved = service.resolve_session(db_session, token)
    assert resolved is not None
    resolved_user, resolved_session = resolved
    assert resolved_user.id == user.id
    assert resolved_session.id == session.id


@pytest.mark.parametrize("token", ["", "not-a-real-token"])
def test_resolve_session_returns_none_for_unknown_token(db_session: Session, token: str):
    assert service.resolve_session(db_session, token) is None


def test_resolve_session_deletes_expired_session(db_session: Session):
    user = _make_user(db_session)
    token, session = service.create_session(db_session, user)
    session.expires_time = datetime.now() - timedelta(seconds=1)
    db_session.commit()

    assert service.resolve_session(db_session, token) is None
    assert db_session.query(LoginSession).count() == 0


def test_resolve_session_rejects_deactivated_user(db_session: Session):
    user = _make_user(db_session)
    token, _session = service.create_session(db_session, user)
    user.is_active = False
    db_session.commit()

    assert service.resolve_session(db_session, token) is None


def test_resolve_session_slides_last_seen_after_interval(db_session: Session):
    user = _make_user(db_session)
    token, session = service.create_session(db_session, user)
    stale = datetime.now() - timedelta(hours=2)
    session.last_seen_time = stale
    db_session.commit()

    service.resolve_session(db_session, token)
    db_session.refresh(session)
    assert session.last_seen_time > stale


# --- 会话管理 ---


def test_list_sessions_only_returns_own(db_session: Session):
    alice = _make_user(db_session, "alice@example.com")
    bob = _make_user(db_session, "bob@example.com")
    service.create_session(db_session, alice)
    service.create_session(db_session, bob)

    sessions = service.list_sessions(db_session, alice.id)
    assert len(sessions) == 1
    assert sessions[0].user_id == alice.id


def test_revoke_session_removes_row(db_session: Session):
    user = _make_user(db_session)
    _token, session = service.create_session(db_session, user)

    service.revoke_session(db_session, user.id, session.id)
    assert db_session.query(LoginSession).count() == 0


def test_revoke_session_treats_other_users_session_as_missing(db_session: Session):
    alice = _make_user(db_session, "alice@example.com")
    bob = _make_user(db_session, "bob@example.com")
    _token, bob_session = service.create_session(db_session, bob)

    with pytest.raises(BusinessError) as exc_info:
        service.revoke_session(db_session, alice.id, bob_session.id)
    assert exc_info.value.code == 404
    assert str(exc_info.value) == "登录会话不存在"
    assert db_session.query(LoginSession).count() == 1


def test_revoke_token_is_idempotent(db_session: Session):
    user = _make_user(db_session)
    token, _session = service.create_session(db_session, user)

    service.revoke_token(db_session, token)
    service.revoke_token(db_session, token)
    service.revoke_token(db_session, "")
    assert db_session.query(LoginSession).count() == 0


# --- 改密 ---


def test_change_password_updates_hash(db_session: Session):
    user = _make_user(db_session)
    service.change_password(db_session, user, "password123", "newpassword456")
    db_session.refresh(user)

    assert verify_password("newpassword456", user.password_hash)
    assert not verify_password("password123", user.password_hash)


def test_change_password_rejects_wrong_old_password(db_session: Session):
    user = _make_user(db_session)
    with pytest.raises(BusinessError) as exc_info:
        service.change_password(db_session, user, "wrong-password", "newpassword456")
    assert str(exc_info.value) == "原密码不正确"


def test_change_password_validates_new_length(db_session: Session):
    user = _make_user(db_session)
    with pytest.raises(BusinessError) as exc_info:
        service.change_password(db_session, user, "password123", "short")
    assert str(exc_info.value) == "密码至少 8 位"


def test_revoke_other_sessions_keeps_current(db_session: Session):
    user = _make_user(db_session)
    _t1, first = service.create_session(db_session, user)
    _t2, second = service.create_session(db_session, user)

    service.revoke_other_sessions(db_session, user.id, keep_session_id=second.id)
    remaining = db_session.query(LoginSession).all()
    assert [s.id for s in remaining] == [second.id]
