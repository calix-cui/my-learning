"""对称加密工具：只用于「代用户保管 API Key」这一种场景。

密钥来自进程环境变量 `APP_SECRET_KEY`（Fernet 要求的 urlsafe-base64 32 字节串，
可用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成）。

没有配置密钥时不抛异常，而是让 `encrypt()` 明确失败、`is_configured()` 返回 False，
由上层决定是「禁止保存」还是「继续用环境变量里的模型」——见 ADR-0009。
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class SecretNotConfiguredError(RuntimeError):
    """服务端没有配置 APP_SECRET_KEY，无法加密/解密用户密钥。"""


def is_configured() -> bool:
    return bool(settings.app_secret_key.get_secret_value())


def _fernet() -> Fernet:
    raw = settings.app_secret_key.get_secret_value()
    if not raw:
        raise SecretNotConfiguredError("服务端未配置 APP_SECRET_KEY")
    try:
        return Fernet(raw.encode())
    except (ValueError, TypeError) as exc:  # 密钥格式不合法
        raise SecretNotConfiguredError(
            "APP_SECRET_KEY 格式不合法，需要 urlsafe-base64 的 32 字节密钥"
        ) from exc


def encrypt(plaintext: str) -> str:
    """返回可直接入库的密文字符串。"""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """密钥换了或密文被改动时会抛 SecretNotConfiguredError，调用方按「需要重填」处理。"""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretNotConfiguredError("无法解密已保存的密钥，请重新填写") from exc
