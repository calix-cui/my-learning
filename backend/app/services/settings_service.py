"""设置模块的业务逻辑：模型配置的读写与连通性自测。

三条纪律（ADR-0009）：
1. Key 只以密文入库，读出时只给末四位；
2. 没有 `APP_SECRET_KEY` 时拒绝保存 Key，但其他字段照常可存；
3. 用户没配过就回落环境变量，并且要让前端知道「当前是继承来的」。
"""

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common import crypto
from app.common.exceptions import BusinessError
from app.config import settings
from app.llm import ModelConfig, build_llm_for, config_from_env, config_from_row
from app.llm.base import ChatMessage, LLMError, LLMTimeoutError
from app.models import UserSettings
from app.schemas.settings import (
    ModelSettingsResponse,
    ModelSettingsUpdateRequest,
    ModelTestRequest,
    ModelTestResponse,
)

# 自测发的内容尽量小：一次十几 token，不烧额度
PING_MESSAGE = "ping"


def get_settings_row(db: Session, user_id: int) -> UserSettings | None:
    return db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))


def _get_or_create(db: Session, user_id: int) -> UserSettings:
    row = get_settings_row(db, user_id)
    if row is not None:
        return row
    row = UserSettings(user_id=user_id)
    db.add(row)
    db.flush()
    return row


def _to_response(row: UserSettings | None) -> ModelSettingsResponse:
    """把库里的行翻译成接口响应；没有行时如实反映环境变量里的默认值。"""
    if row is None:
        env = config_from_env()
        return ModelSettingsResponse(
            provider=env.provider,  # type: ignore[arg-type]
            base_url=env.base_url or None,
            model=env.model or None,
            timeout_seconds=int(env.timeout_seconds),
            has_api_key=bool(env.api_key),
            api_key_hint=None,
            can_store_api_key=crypto.is_configured(),
            inherited_from_env=True,
            update_time=None,
        )

    return ModelSettingsResponse(
        provider=row.model_provider,  # type: ignore[arg-type]
        base_url=row.model_base_url,
        model=row.model_name,
        timeout_seconds=row.model_timeout_seconds,
        has_api_key=bool(row.model_api_key_ciphertext),
        api_key_hint=row.model_api_key_hint,
        can_store_api_key=crypto.is_configured(),
        inherited_from_env=False,
        update_time=row.update_time,
    )


def read_model_settings(db: Session, user_id: int) -> ModelSettingsResponse:
    return _to_response(get_settings_row(db, user_id))


def update_model_settings(
    db: Session, user_id: int, payload: ModelSettingsUpdateRequest
) -> ModelSettingsResponse:
    row = _get_or_create(db, user_id)
    changes = payload.model_dump(exclude_unset=True)

    api_key = changes.pop("api_key", None)
    if api_key is not None:
        if api_key == "":
            # 显式清除
            row.model_api_key_ciphertext = None
            row.model_api_key_hint = None
        else:
            if not crypto.is_configured():
                raise BusinessError("服务端未配置 APP_SECRET_KEY，无法保存自定义 Key", code=400)
            row.model_api_key_ciphertext = crypto.encrypt(api_key)
            row.model_api_key_hint = api_key[-4:]

    if "provider" in changes and changes["provider"]:
        row.model_provider = changes["provider"]
    if "base_url" in changes:
        row.model_base_url = changes["base_url"] or None
    if "model" in changes:
        row.model_name = changes["model"] or None
    if "timeout_seconds" in changes and changes["timeout_seconds"] is not None:
        row.model_timeout_seconds = int(changes["timeout_seconds"])

    # 选 openai 时必须能凑齐三件套（Key 可以是库里已存的或环境变量里的）
    if row.model_provider == "openai":
        effective = config_from_row(row)
        missing: list[str] = []
        if not effective.base_url:
            missing.append("Base URL")
        if not effective.model:
            missing.append("模型名")
        if not effective.api_key:
            missing.append("API Key")
        if missing:
            db.rollback()
            raise BusinessError(f"选择 OpenAI 兼容服务需要填写：{'、'.join(missing)}", code=400)

    db.commit()
    db.refresh(row)
    return _to_response(row)


def _merge_test_config(db: Session, user_id: int, payload: ModelTestRequest) -> ModelConfig:
    """自测用的配置：库里已保存的 + 本次提交里覆盖的部分。"""
    row = get_settings_row(db, user_id)
    base = config_from_row(row)
    changes = payload.model_dump(exclude_unset=True)

    return ModelConfig(
        provider=changes.get("provider") or base.provider,
        base_url=(changes.get("base_url") if "base_url" in changes else base.base_url) or "",
        api_key=(changes.get("api_key") or base.api_key) or "",
        model=(changes.get("model") if "model" in changes else base.model) or "",
        timeout_seconds=float(
            changes.get("timeout_seconds")
            if changes.get("timeout_seconds") is not None
            else base.timeout_seconds
        ),
    )


def test_model_settings(db: Session, user_id: int, payload: ModelTestRequest) -> ModelTestResponse:
    config = _merge_test_config(db, user_id, payload)
    started = time.perf_counter()

    try:
        client = build_llm_for(config)
        reply = client.chat([ChatMessage(role="user", content=PING_MESSAGE)])
    except LLMTimeoutError as exc:
        return ModelTestResponse(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=config.model or None,
            message=str(exc) or "模型服务超时",
        )
    except LLMError as exc:
        return ModelTestResponse(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=config.model or None,
            message=str(exc) or "模型服务不可用",
        )

    return ModelTestResponse(
        ok=True,
        latency_ms=int((time.perf_counter() - started) * 1000),
        model=reply.get("model") or config.model or None,
        message="连接正常",
    )


def decrypt_api_key(row: UserSettings | None) -> str | None:  # pragma: no cover - 调试用
    """仅供排障脚本使用；接口层永远不调用它。"""
    if row is None or not row.model_api_key_ciphertext:
        return None
    return crypto.decrypt(row.model_api_key_ciphertext)


def effective_settings_snapshot() -> dict[str, Any]:  # pragma: no cover - 调试用
    """打印环境变量侧的生效配置（不含明文 Key），用于运维排查。"""
    env = config_from_env()
    return {
        "provider": env.provider,
        "base_url": env.base_url,
        "model": env.model,
        "timeout_seconds": env.timeout_seconds,
        "has_api_key": bool(env.api_key),
        "app_secret_key_configured": crypto.is_configured(),
        "app_env": settings.app_env,
    }
