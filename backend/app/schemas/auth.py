"""账号接口的数据契约。

时间字段统一序列化成 `YYYY-MM-DD HH:MM:SS`，与对话接口保持一致。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="登录邮箱，服务端会统一转小写")
    password: str = Field(min_length=8, max_length=72, description="密码，8–72 位")
    display_name: str | None = Field(
        default=None, max_length=50, description="显示名，可空，界面回落到邮箱"
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None
    role: str

    @field_serializer("display_name")
    def _serialize_display_name(self, value: str | None) -> str | None:
        return value or None


class UserDetailResponse(UserResponse):
    create_time: datetime
    last_login_time: datetime | None

    @field_serializer("create_time", "last_login_time")
    def _serialize_time(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_agent: str | None
    ip: str | None
    create_time: datetime
    last_seen_time: datetime
    expires_time: datetime
    # 由接口层填充：是否是「当前这台设备」
    is_current: bool = False

    @field_serializer("create_time", "last_seen_time", "expires_time")
    def _serialize_time(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
