"""创建（或重置）管理员账号：部署到公网后用它建第一个账号，避免注册接口被陌生人抢先。

用法（在 backend/ 下）：

    ADMIN_EMAIL=me@example.com ADMIN_PASSWORD='至少8位的密码' uv run python -m app.create_admin

行为：
- 邮箱不存在 → 新建 admin 并打印提示；
- 邮箱已存在 → 更新密码并确保 role=admin、is_active=true（用于忘记密码时救急）。
"""

import os
import sys

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.auth.service import _validate_password, normalize_email
from app.common.exceptions import BusinessError
from app.database import SessionLocal
from app.models import User


def main() -> int:
    email = (os.environ.get("ADMIN_EMAIL") or "").strip()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if not email or not password:
        print("请通过环境变量提供管理员账号：")
        print(
            "  ADMIN_EMAIL=me@example.com ADMIN_PASSWORD='至少8位的密码' uv run python -m app.create_admin"
        )
        return 1

    try:
        password = _validate_password(password)
    except BusinessError as exc:
        print(f"密码不符合要求：{exc}")
        return 1

    normalized = normalize_email(email)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == normalized))
        if user is None:
            user = User(
                email=normalized,
                password_hash=hash_password(password),
                display_name=None,
                role="admin",
                is_active=True,
            )
            db.add(user)
            action = "已创建管理员账号"
        else:
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
            action = "已更新该账号为管理员并重置密码"
        db.commit()
        db.refresh(user)
        print(f"{action}：{user.email}（id={user.id}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
