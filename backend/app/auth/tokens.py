"""登录令牌：生成随机令牌、只存摘要。

- 令牌本体只出现在 Cookie 里，数据库存 SHA-256 摘要；
- 校验时对收到的令牌算摘要再查库，泄库也拿不到可用令牌；
- 用 `secrets.token_urlsafe`（密码学安全随机）而不是 uuid4。
"""

import hashlib
import secrets

# 32 字节随机 → 43 个字符的 URL-safe 字符串，熵足够
TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 摘要（64 位十六进制）。这里不需要加盐：令牌本身是 256 位随机数。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
