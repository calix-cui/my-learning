"""Agent 运行接口：流式跑一次循环，并回放历史运行。

和对话接口的关系：普通对话走 `/messages/stream`（一问一答）；
需要查资料/算数时走这里，多一个「工具往返」的过程，逐步可见。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.executor import prepare_run, stream_run
from app.agent.tools import build_registry
from app.api.sse import SSE_HEADERS, encode_sse
from app.auth.dependencies import CurrentUser
from app.common.response import Response
from app.dependencies import get_db
from app.llm import LLMClient, get_user_llm
from app.models import AgentRun
from app.schemas.agent import AgentMessageRequest, AgentRunListResponse
from app.services import chat_service

router = APIRouter(prefix="/conversations", tags=["Agent 接口"])


@router.post(
    "/{conversation_id}/agent/stream",
    summary="发送消息（agent 循环，流式）",
    description=(
        "跑一次「模型 → 工具 → 模型」循环，以 SSE 逐步返回过程与最终答复。"
        "事件类型：run_started / assistant_text / tool_call / tool_result / run_finished / error。"
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
    events = stream_run(
        db,
        run=run,
        conversation=conversation,
        messages=messages,
        llm=llm,
        is_first_message=is_first,
        user_id=user.id,
        registry=build_registry(db),
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
