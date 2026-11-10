"""Agent 运行接口：流式跑一次循环，并回放历史运行。

和对话接口的关系：普通对话走 `/messages/stream`（一问一答）；
需要查资料/算数时走这里，多一个「工具往返」的过程，逐步可见。
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
from app.api.sse import SSE_HEADERS, encode_sse
from app.auth.dependencies import CurrentUser
from app.common.exceptions import BusinessError
from app.common.response import Response
from app.dependencies import get_db
from app.llm import LLMClient, get_user_llm
from app.models import AgentApproval, AgentRun
from app.schemas.agent import (
    AgentApprovalListResponse,
    AgentMessageRequest,
    AgentRunListResponse,
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
        "approval_required / run_finished / error。"
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
    # 先同步做校验与落库：404/400/409 仍是普通 JSON，只有真正开始循环后才进 SSE
    conversation, run, messages, is_first = prepare_run(
        db, user_id=user.id, conversation_id=conversation_id, content=payload.content
    )
    registry = registry_for(db, user.id)
    events = stream_run(
        db,
        run=run,
        conversation=conversation,
        messages=messages,
        llm=llm,
        is_first_message=is_first,
        user_id=user.id,
        registry=registry,
        policy=build_policy(db, user_id=user.id, registry=registry, run=run),
    )
    return StreamingResponse(
        encode_sse(events), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get(
    "/{conversation_id}/agent/runs",
    response_model=Response,
    summary="查看历史运行",
    description="返回该会话最近的运行记录与步骤，用于刷新后回放时间线。",
)
def list_agent_runs(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20, description="最多返回几条")] = 5,
):
    # 先校验会话归属：别人的会话在这里就 404，不会漏出运行记录
    chat_service.get_conversation(db, user.id, conversation_id)
    rows = db.scalars(
        select(AgentRun)
        .where(AgentRun.conversation_id == conversation_id)
        .options(selectinload(AgentRun.steps))
        .order_by(AgentRun.id.desc())
        .limit(limit)
    ).all()
    return Response.success(data=AgentRunListResponse.model_validate({"items": list(rows)}))


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
    registry = registry_for(db, user.id)
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
