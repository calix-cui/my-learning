"""设置服务层测试：加密存 Key、回落环境变量、连通性自测。

这里不碰网络：自测接口在 provider=fake 时走 FakeLLM，openai 缺项时直接返回 ok=False。
"""

import pytest
from cryptography.fernet import Fernet

from app.common import crypto
from app.common.exceptions import BusinessError
from app.config import Settings, settings
from app.schemas.settings import ModelSettingsUpdateRequest, ModelTestRequest
from app.services import settings_service


@pytest.fixture()
def secret_key(monkeypatch):
    """给用例装一把临时主密钥，测完自动还原。"""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "app_secret_key", Settings.model_fields["app_secret_key"].default)
    monkeypatch.setattr(settings, "app_secret_key", type(settings.app_secret_key)(key))
    assert crypto.is_configured() is True
    return key


@pytest.fixture()
def no_secret_key(monkeypatch):
    monkeypatch.setattr(settings, "app_secret_key", type(settings.app_secret_key)(""))
    assert crypto.is_configured() is False


def test_read_without_row_falls_back_to_env(db_session, user):
    data = settings_service.read_model_settings(db_session, user.id)

    assert data.inherited_from_env is True
    assert data.provider in {"fake", "openai"}
    assert data.update_time is None


def test_update_fake_provider_creates_row(db_session, user):
    data = settings_service.update_model_settings(
        db_session, user.id, ModelSettingsUpdateRequest(provider="fake", timeout_seconds=42)
    )

    assert data.provider == "fake"
    assert data.timeout_seconds == 42
    assert data.inherited_from_env is False
    assert data.update_time is not None

    row = settings_service.get_settings_row(db_session, user.id)
    assert row is not None and row.user_id == user.id


@pytest.mark.usefixtures("no_secret_key")
def test_update_api_key_requires_secret_key(db_session, user):
    with pytest.raises(BusinessError) as excinfo:
        settings_service.update_model_settings(
            db_session,
            user.id,
            ModelSettingsUpdateRequest(provider="fake", api_key="sk-test-1234"),
        )

    assert "APP_SECRET_KEY" in str(excinfo.value)
    assert excinfo.value.code == 400


@pytest.mark.usefixtures("secret_key")
def test_update_api_key_stores_ciphertext_and_hint(db_session, user):
    data = settings_service.update_model_settings(
        db_session,
        user.id,
        ModelSettingsUpdateRequest(
            provider="openai",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key="sk-test-abcd",
        ),
    )

    assert data.has_api_key is True
    assert data.api_key_hint == "abcd"
    assert data.can_store_api_key is True

    row = settings_service.get_settings_row(db_session, user.id)
    assert row is not None
    assert row.model_api_key_ciphertext is not None
    assert "sk-test-abcd" not in row.model_api_key_ciphertext
    assert crypto.decrypt(row.model_api_key_ciphertext) == "sk-test-abcd"


@pytest.mark.usefixtures("secret_key")
def test_update_with_empty_api_key_clears_it(db_session, user):
    settings_service.update_model_settings(
        db_session, user.id, ModelSettingsUpdateRequest(api_key="sk-test-abcd")
    )
    data = settings_service.update_model_settings(
        db_session, user.id, ModelSettingsUpdateRequest(api_key="")
    )

    assert data.has_api_key is False
    assert data.api_key_hint is None


@pytest.mark.usefixtures("secret_key")
def test_update_openai_missing_fields_rolls_back(db_session, user):
    with pytest.raises(BusinessError) as excinfo:
        settings_service.update_model_settings(
            db_session, user.id, ModelSettingsUpdateRequest(provider="openai")
        )

    assert "Base URL" in str(excinfo.value)
    assert settings_service.get_settings_row(db_session, user.id) is None


@pytest.mark.usefixtures("secret_key")
def test_update_openai_with_saved_key_is_allowed(db_session, user):
    settings_service.update_model_settings(
        db_session, user.id, ModelSettingsUpdateRequest(api_key="sk-existing-9999")
    )
    data = settings_service.update_model_settings(
        db_session,
        user.id,
        ModelSettingsUpdateRequest(
            provider="openai", base_url="https://api.deepseek.com/v1", model="deepseek-chat"
        ),
    )

    assert data.provider == "openai"
    assert data.has_api_key is True


def test_test_model_uses_fake(db_session, user):
    result = settings_service.test_model_settings(
        db_session, user.id, ModelTestRequest(provider="fake")
    )

    assert result.ok is True
    assert result.latency_ms >= 0
    assert "收到" in result.message or result.message == "连接正常"


@pytest.mark.usefixtures("no_secret_key")
def test_test_model_openai_without_key_reports_reason(db_session, user):
    result = settings_service.test_model_settings(
        db_session,
        user.id,
        ModelTestRequest(
            provider="openai", base_url="https://api.deepseek.com/v1", model="deepseek-chat"
        ),
    )

    assert result.ok is False
    assert "API Key" in result.message


@pytest.mark.usefixtures("secret_key")
def test_test_model_overrides_saved_settings(db_session, user):
    settings_service.update_model_settings(
        db_session, user.id, ModelSettingsUpdateRequest(provider="fake", timeout_seconds=10)
    )
    result = settings_service.test_model_settings(
        db_session, user.id, ModelTestRequest(provider="fake", timeout_seconds=99)
    )

    assert result.ok is True
    row = settings_service.get_settings_row(db_session, user.id)
    # 自测不落库
    assert row is not None and row.model_timeout_seconds == 10


@pytest.mark.usefixtures("secret_key")
def test_decrypt_with_broken_ciphertext_falls_back(db_session, user):
    settings_service.update_model_settings(
        db_session,
        user.id,
        ModelSettingsUpdateRequest(
            provider="openai",
            base_url="https://api.deepseek.com/v1",
            model="m",
            api_key="sk-x-0001",
        ),
    )
    row = settings_service.get_settings_row(db_session, user.id)
    assert row is not None
    row.model_api_key_ciphertext = "not-a-valid-token"
    db_session.commit()

    from app.llm import config_from_row

    config = config_from_row(row)
    assert config.api_key == ""
