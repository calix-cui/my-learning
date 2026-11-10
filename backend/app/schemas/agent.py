"""Agent 接口的数据契约。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class AgentMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000, description="用户消息")


class AgentStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int = Field(description="第几步，从 1 开始")
    kind: str = Field(description="user_message/assistant_text/tool_call/tool_result/final_answer")
    content: str | None = Field(default=None, description="文本或工具结果")
    tool_name: str | None = Field(default=None, description="工具名")
    tool_args: dict | None = Field(default=None, description="工具参数")
    ok: bool | None = Field(default=None, description="工具是否成功")
    duration_ms: int | None = Field(default=None, description="工具耗时毫秒")
    create_time: datetime

    @field_serializer("create_time")
    def serialize_time(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["running", "completed", "failed", "cancelled"] = Field(description="运行状态")
    step_count: int = Field(description="已执行步数")
    model: str | None = Field(default=None, description="实际使用的模型")
    started_time: datetime
    finished_time: datetime | None = None
    error_message: str | None = Field(default=None, description="失败原因")
    steps: list[AgentStepResponse] = Field(default_factory=list, description="按 seq 排序的步骤")

    @field_serializer("started_time", "finished_time")
    def serialize_time(self, value: datetime | None) -> str | None:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class AgentRunListResponse(BaseModel):
    items: list[AgentRunResponse]


__all__ = [
    "AgentMessageRequest",
    "AgentRunListResponse",
    "AgentRunResponse",
    "AgentStepResponse",
]
