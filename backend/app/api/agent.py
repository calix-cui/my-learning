"""Agent 运行接口：流式跑一次循环，并回放历史运行。

聊天页使用 `/messages/stream` 的自动执行模式。旧 Agent 入口和审批续跑
复用同一执行循环，保留各自的 SSE 契约。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.executor import (
    build_policy,
    decide_approval,
    prepare_run,
    registry_for,
    resume_run,
    stream_run,
)
from app.agent.tools import ToolRegistry
from app.api.sse import SSE_HEADERS, encode_sse
from app.auth.dependencies import CurrentUser
from app.common.exceptions import BusinessError
from app.common.response import Response
from app.dependencies import get_db
from app.llm import LLMClient, get_user_llm
from app.llm.base import ReasoningEffort
from app.models import AgentApproval, AgentRun
from app.models.agent_step import REPLAY_STEP_KINDS
from app.schemas.agent import (
    AgentApprovalListResponse,
    AgentMessageRequest,
    AgentRunListResponse,
    AgentRunResponse,
    AgentStepListResponse,
    AgentStepResponse,
    ApprovalDecisionRequest,
)
from app.services import chat_service

router = APIRouter(prefix="/conversations", tags=["Agent 接口"])
approvals_router = APIRouter(prefix="/agent", tags=["Agent 审批"])


@router.post(
    "/{conversation_id}/agent/stream",
    summary="发送消息（agent 循环，流式）",
    description=(
        "跑一次「模型 → 工具 → 模型」循环，以 SSE 逐步返回过程与最终答复。"
        "事件类型：run_started / assistant_text / tool_call / tool_result / "
        "skill_loaded / skill_load_failed / approval_required / run_finished / error。"
        "需要审批时流会在 approval_required 之后结束，决定后调用审批接口接着往下跑。"
    ),
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE 事件流"}},
)
def stream_agent_run(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    payload: AgentMessageRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMClient, Depends(get_user_llm)],
):
    return agent_stream_response(
        db, llm, user.id, conversation_id, content=payload.content, skill_mode=payload.skill_mode
    )


def agent_stream_response(
    db: Session,
    llm: LLMClient,
    user_id: int,
    conversation_id: int,
    *,
    content: str,
    skill_mode: str,
    reasoning_effort: ReasoningEffort | None = None,
    request_id: str | None = None,
    skill_keys: list[str] | None = None,
    skill_catalog_version: str | None = None,
) -> StreamingResponse:
    # 先同步做校验与落库：404/400/409 仍是普通 JSON，只有真正开始循环后才进 SSE
    conversation, run, messages, is_first = prepare_run(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        content=content,
        skill_mode=skill_mode,
        reasoning_effort=reasoning_effort,
        request_id=request_id,
        skill_keys=skill_keys,
        skill_catalog_version=skill_catalog_version,
    )
    # 按当前用户和会话装配工具，再将注册表与执行策略交给 Agent 循环。
    registry = (
        registry_for(db, user_id, conversation.id)
        if getattr(llm, "supports_tool_calls", True)
        else ToolRegistry([])
    )
    events = stream_run(
        db,
        run=run,
        conversation=conversation,
        messages=messages,
        llm=llm,
        is_first_message=is_first,
        user_id=user_id,
        registry=registry,
        policy=build_policy(db, user_id=user_id, registry=registry, run=run),
    )
    return StreamingResponse(
        encode_sse(events), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get(
    "/{conversation_id}/agent/runs",
    response_model=Response,
    summary="查看历史运行",
    description=(
        "返回该会话最近的运行记录与步骤，用于刷新后回放时间线。"
        "带 `request_id` 时只按该请求 ID 查一次运行（断线后核对「我这条发出去没有」）；"
        "查不到返回 404，表示这次提交没有落库，可以安全重发。"
    ),
)
def list_agent_runs(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20, description="最多返回几条")] = 5,
    request_id: Annotated[
        str | None, Query(max_length=36, description="按客户端请求 ID 精确定位一次运行")
    ] = None,
):
    # 先校验会话归属：别人的会话在这里就 404，不会漏出运行记录
    chat_service.get_conversation(db, user.id, conversation_id)
    statement = select(AgentRun).where(AgentRun.conversation_id == conversation_id)
    if request_id is not None:
        # 同一会话内 request_id 有唯一约束，这里最多一条
        statement = statement.where(AgentRun.request_id == request_id)
    rows = db.scalars(
        statement.options(selectinload(AgentRun.steps)).order_by(AgentRun.id.desc()).limit(limit)
    ).all()
    if request_id is not None and not rows:
        raise BusinessError("这次提交还没有落库，可以重新发送", code=404)
    return Response.success(data=AgentRunListResponse.model_validate({"items": list(rows)}))


@approvals_router.get(
    "/runs/{run_id}",
    response_model=Response,
    summary="查看某次运行",
    description=(
        "一个请求同时回答「跑到哪了」和「跑了什么」：运行状态、失败原因、结束时间与全部步骤。"
        "断线后前端用它定点核对，不必再拉整页历史。"
    ),
)
def get_agent_run(
    run_id: Annotated[int, Path(gt=0, description="运行ID")],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.user_id == user.id)
        .options(selectinload(AgentRun.steps))
    )
    if run is None:
        # 与其它接口一致：不是自己的运行一律 404，不暴露存在性
        raise BusinessError("运行不存在", code=404)
    return Response.success(data=AgentRunResponse.model_validate(run))


@approvals_router.get(
    "/runs/{run_id}/steps",
    response_model=Response,
    summary="查看某次运行的执行步骤",
    description=(
        "按 `seq` 升序返回可见步骤，同时带上运行状态。"
        "带 `since_seq` 时只返回该步之后的增量，用于断线后的低开销轮询。"
    ),
)
def get_replay_steps(
    run_id: Annotated[int, Path(gt=0, description="运行ID")],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    since_seq: Annotated[int | None, Query(ge=0, description="只返回 seq 大于它的步骤")] = None,
):
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.user_id == user.id)
        .options(selectinload(AgentRun.steps))
    )
    if run is None:
        raise BusinessError("运行不存在", code=404)
    visible = [step for step in run.steps if step.kind in REPLAY_STEP_KINDS]
    return Response.success(
        data=AgentStepListResponse(
            items=[
                AgentStepResponse.model_validate(step)
                for step in visible
                if since_seq is None or step.seq > since_seq
            ],
            status=run.status,
            visible_step_count=len(visible),
            error_message=run.error_message,
            finished_time=run.finished_time,
        )
    )


@approvals_router.get(
    "/runs/{run_id}/approvals",
    response_model=Response,
    summary="查看某次运行的审批",
    description="默认返回全部（含已决），用于刷新页面后把审批卡片复原。",
)
def list_approvals(
    run_id: Annotated[int, Path(gt=0, description="运行ID")],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user.id))
    if run is None:
        # 与其它接口一致：不是自己的运行一律 404，不暴露存在性
        raise BusinessError("运行不存在", code=404)
    rows = db.scalars(
        select(AgentApproval).where(AgentApproval.run_id == run_id).order_by(AgentApproval.seq)
    ).all()
    return Response.success(data=AgentApprovalListResponse(items=list(rows)))


@approvals_router.post(
    "/runs/{run_id}/approvals/{approval_id}",
    summary="批准或拒绝一次工具调用（流式继续跑）",
    description=(
        "记录决定后从库里重放上下文继续执行，返回 SSE 事件流（与 agent/stream 同格式）。"
        "开流之前能判的错误（404/409）仍是普通 JSON。"
    ),
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE 事件流"}},
)
def decide(
    run_id: Annotated[int, Path(gt=0, description="运行ID")],
    approval_id: Annotated[int, Path(gt=0, description="审批ID")],
    payload: ApprovalDecisionRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMClient, Depends(get_user_llm)],
):
    run, approval = decide_approval(
        db,
        user_id=user.id,
        run_id=run_id,
        approval_id=approval_id,
        approved=payload.decision == "approve",
        note=payload.note,
    )
    # 审批续跑按当前账号工具设置重新核对工具和权限。
    registry = registry_for(db, user.id, run.conversation_id)
    events = resume_run(
        db,
        run=run,
        approval=approval,
        llm=llm,
        user_id=user.id,
        note=payload.note,
        registry=registry,
        policy=build_policy(db, user_id=user.id, registry=registry, run=run),
    )
    return StreamingResponse(
        encode_sse(events), media_type="text/event-stream", headers=SSE_HEADERS
    )
