"""模型客户端入口：配置解析 + 依赖注入。

配置优先级（ADR-0009）：用户设置（`user_settings`）> 进程环境变量。
业务代码统一 `from app.llm import get_user_llm`；测试里用
`app.dependency_overrides[get_user_llm] = lambda: FakeLLM(...)` 直接替换。
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.config import settings
from app.dependencies import get_db
from app.llm.base import ChatMessage, LLMClient, LLMError, LLMReply, LLMTimeoutError
from app.llm.fake import FakeLLM
from app.llm.openai_compatible import OpenAICompatibleClient

__all__ = [
    "ChatMessage",
    "LLMClient",
    "LLMError",
    "LLMReply",
    "LLMTimeoutError",
    "ModelConfig",
    "build_llm",
    "build_llm_for",
    "config_from_env",
    "config_from_row",
    "get_llm",
    "get_user_llm",
    "resolve_llm",
]


@dataclass(frozen=True)
class ModelConfig:
    """一次模型调用需要的全部信息（已解密，不要落日志）。"""

    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float


def config_from_env() -> ModelConfig:
    """环境变量那套配置：没有用户设置时的默认值。"""
    return ModelConfig(
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def config_from_row(row: object | None) -> ModelConfig:
    """把 `user_settings` 行转成配置。row 为空时回落环境变量。

    解密失败（换了 APP_SECRET_KEY）按「没有 key」处理，由调用方报出可读错误，
    不让解密异常一路冒到 500。
    """
    if row is None:
        return config_from_env()

    from app.common import crypto

    ciphertext = getattr(row, "model_api_key_ciphertext", None)
    api_key = ""
    if ciphertext:
        try:
            api_key = crypto.decrypt(ciphertext)
        except crypto.SecretNotConfiguredError:
            api_key = ""

    return ModelConfig(
        provider=getattr(row, "model_provider", None) or settings.llm_provider,
        base_url=getattr(row, "model_base_url", None) or settings.llm_base_url,
        api_key=api_key,
        model=getattr(row, "model_name", None) or settings.llm_model,
        timeout_seconds=float(
            getattr(row, "model_timeout_seconds", None) or settings.llm_timeout_seconds
        ),
    )


def build_llm_for(config: ModelConfig) -> LLMClient:
    """按给定配置构造客户端；配置不完整时抛 LLMError（消息面向用户）。"""
    if config.provider != "openai":
        return FakeLLM(delay_seconds=settings.llm_fake_delay_seconds)

    if not config.base_url or not config.model:
        raise LLMError("请先在设置里填写 Base URL 与模型名")
    if not config.api_key:
        raise LLMError("请先在设置里填写 API Key")

    return OpenAICompatibleClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )


def build_llm() -> LLMClient:
    """按环境变量构造实现。生产只缓存一次，避免每个请求新建 httpx 连接池。"""
    return build_llm_for(config_from_env())


@lru_cache
def get_llm() -> LLMClient:
    """环境变量默认实现（测试与「没有用户设置」的场景用）。"""
    return build_llm()


def resolve_llm(db: Session, user_id: int) -> LLMClient:
    """按用户设置构造客户端；用户没配过就用环境变量。"""
    from app.services import settings_service

    row = settings_service.get_settings_row(db, user_id)
    return build_llm_for(config_from_row(row))


def get_user_llm(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> LLMClient:
    """FastAPI 依赖：每个请求按当前用户的配置选模型。

    测试里替换它即可：`app.dependency_overrides[get_user_llm] = lambda: FakeLLM()`。
    """
    return resolve_llm(db, user.id)
