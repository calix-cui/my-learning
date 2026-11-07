from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(
        default=None, max_length=100, description="会话标题，缺省为「新会话」"
    )


class ConversationUpdateRequest(BaseModel):
    """重命名。纯空白的判断在 service 层（schema 只看长度）。"""

    title: str = Field(min_length=1, max_length=100, description="新标题")


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="消息ID")
    conversation_id: int = Field(description="所属会话ID")
    role: str = Field(description="角色：user / assistant / system")
    content: str = Field(description="消息正文")
    model: str | None = Field(description="生成该回复的模型；用户消息为空")
    create_time: datetime = Field(description="创建时间")

    @field_serializer("create_time")
    def serialize_create_time(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="会话ID")
    title: str = Field(description="会话标题")
    agent_key: str = Field(description="所属代理标识")
    update_time: datetime = Field(description="最后活动时间")
    create_time: datetime = Field(description="创建时间")

    @field_serializer("update_time", "create_time")
    def serialize_datetime(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class ConversationListItemResponse(ConversationResponse):
    """列表项比详情少一层消息，但多一个消息数，省得前端为每行再发一次请求。"""

    message_count: int = Field(description="该会话的消息条数")


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = Field(description="该会话的全部消息，按发送顺序")


class ConversationPageResponse(BaseModel):
    items: list[ConversationListItemResponse] = Field(description="当前页会话")
    total: int = Field(description="会话总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
