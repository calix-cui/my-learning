"""密码哈希：只做两件事——把明文变成可存储的哈希、用哈希校验明文。

算法用 Argon2id（OWASP 首选）。参数交给 argon2-cffi 的默认值，
哈希串里自带算法与参数，将来调参或换算法时旧密码仍然能验证。
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# 单例：PasswordHasher 内部缓存了参数，重复构造没有意义
_hasher = PasswordHasher()


def hash_password(raw_password: str) -> str:
    """返回形如 `$argon2id$v=19$m=65536,t=3,p=4$...` 的哈希串。"""
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    """校验明文与哈希是否匹配；哈希损坏或算法不认识时一律当作不匹配。"""
    try:
        return _hasher.verify(password_hash, raw_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """哈希参数过旧时返回 True，登录成功后可顺手升级（当前参数未变，恒为 False）。"""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False
