"""Agent 接口的数据契约。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class AgentMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000, description="用户消息")
    skill_mode: Literal["off", "manual", "auto"] = Field(
        default="manual", description="Skill 使用方式"
    )


class AgentStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int = Field(description="第几步，从 1 开始")
    kind: str = Field(
        description="user_message/assistant_text/tool_call/tool_result/skill_loaded/skill_load_failed/final_answer"
    )
    content: str | None = Field(default=None, description="文本或工具结果")
    tool_name: str | None = Field(default=None, description="工具名")
    tool_args: dict | None = Field(default=None, description="工具参数")
    skill_key: str | None = Field(default=None, description="Skill 稳定标识")
    skill_name: str | None = Field(default=None, description="Skill 名称")
    skill_source: str | None = Field(default=None, description="Skill 来源")
    skill_version: str | None = Field(default=None, description="Skill 内容版本")
    ok: bool | None = Field(default=None, description="工具是否成功")
    duration_ms: int | None = Field(default=None, description="工具耗时毫秒")
    create_time: datetime

    @field_serializer("create_time")
    def serialize_time(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class AgentRunSummary(BaseModel):
    id: int
    user_message_id: int | None
    assistant_message_id: int | None
    status: Literal["running", "waiting_approval", "completed", "failed", "cancelled"]
    visible_step_count: int
    request_id: str | None = Field(
        default=None, description="客户端提交时的请求 ID，用于把断线后的核对对齐到具体一次运行"
    )
    error_message: str | None = Field(default=None, description="失败原因（与库中记录一致）")
    finished_time: datetime | None = Field(default=None, description="结束时间")

    @field_serializer("finished_time")
    def serialize_finished_time(self, value: datetime | None) -> str | None:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int = Field(description="所属会话")
    user_message_id: int | None = None
    assistant_message_id: int | None = None
    status: Literal["running", "waiting_approval", "completed", "failed", "cancelled"] = Field(
        description="运行状态"
    )
    step_count: int = Field(description="已执行步数")
    model: str | None = Field(default=None, description="实际使用的模型")
    request_id: str | None = Field(default=None, description="客户端请求 ID")
    started_time: datetime
    finished_time: datetime | None = None
    error_message: str | None = Field(default=None, description="失败原因")
    steps: list[AgentStepResponse] = Field(default_factory=list, description="按 seq 排序的步骤")

    @field_serializer("started_time", "finished_time")
    def serialize_time(self, value: datetime | None) -> str | None:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class AgentRunListResponse(BaseModel):
    items: list[AgentRunResponse]


class AgentStepListResponse(BaseModel):
    """步骤 + 运行状态一起返回：轮询一次就够判断「有新步骤吗」「跑完了吗」。"""

    items: list[AgentStepResponse]
    status: Literal["running", "waiting_approval", "completed", "failed", "cancelled"]
    visible_step_count: int = Field(description="该运行可见步骤总数（不受 since_seq 影响）")
    error_message: str | None = Field(default=None, description="失败原因")
    finished_time: datetime | None = Field(default=None, description="结束时间")

    @field_serializer("finished_time")
    def serialize_finished_time(self, value: datetime | None) -> str | None:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"] = Field(description="批准或拒绝")
    note: str | None = Field(default=None, max_length=255, description="决定理由，可空")


class AgentApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    seq: int = Field(description="对应 agent_steps.seq")
    tool_name: str
    tool_args: dict | None = Field(default=None, description="要执行什么，给用户看清楚")
    status: Literal["pending", "approved", "rejected", "expired"]
    note: str | None = Field(default=None, description="挂起原因或用户填的理由")
    decided_time: datetime | None = None
    create_time: datetime

    @field_serializer("decided_time", "create_time")
    def serialize_time(self, value: datetime | None) -> str | None:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class AgentApprovalListResponse(BaseModel):
    items: list[AgentApprovalResponse]


__all__ = [
    "AgentApprovalListResponse",
    "AgentApprovalResponse",
    "AgentMessageRequest",
    "AgentRunListResponse",
    "AgentRunResponse",
    "AgentRunSummary",
    "AgentStepListResponse",
    "AgentStepResponse",
    "ApprovalDecisionRequest",
]
