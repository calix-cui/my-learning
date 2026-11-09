"""设置相关的数据契约。

约定：
- 读接口永远不返回 Key 明文，只给 `has_api_key` 与末四位 `api_key_hint`；
- 写接口里 `api_key` 的三态：字段缺省 / `null` = 保持不变，空字符串 = 清除，其他 = 更新。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

ModelProvider = Literal["fake", "openai"]


class ModelSettingsResponse(BaseModel):
    """当前用户的模型配置（不含明文 Key）。"""

    provider: ModelProvider
    base_url: str | None = None
    model: str | None = None
    timeout_seconds: int
    has_api_key: bool
    api_key_hint: str | None = None
    # 服务端是否配置了 APP_SECRET_KEY；前端据此提示「能不能保存自定义 Key」
    can_store_api_key: bool
    # 没有用户配置时实际生效的是环境变量那套，前端要能区分
    inherited_from_env: bool
    update_time: datetime | None = None

    @field_serializer("update_time")
    def _fmt_time(self, value: datetime | None) -> str | None:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class ModelSettingsUpdateRequest(BaseModel):
    """保存模型配置：只有显式传了的字段才会改。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: ModelProvider | None = None
    base_url: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=64)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    api_key: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _check_openai_fields(self) -> "ModelSettingsUpdateRequest":
        # provider 改成 openai 时，base_url / model 必须一起给（Key 可以是已保存的那把）
        if self.provider != "openai":
            return self
        if self.base_url is not None and not self.base_url:
            raise ValueError("Base URL 不能为空")
        return self


class ModelTestRequest(BaseModel):
    """连通性自测：可以用「库里已保存的配置」，也可以带本次还没保存的临时值。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: ModelProvider | None = None
    base_url: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=64)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    # 不传 = 用已保存的 Key；传空串没有意义，按未传处理
    api_key: str | None = Field(default=None, max_length=512)


class ModelTestResponse(BaseModel):
    ok: bool
    latency_ms: int
    model: str | None = None
    message: str
