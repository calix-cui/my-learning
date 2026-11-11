from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.sse import SSE_HEADERS, encode_sse
from app.auth.dependencies import CurrentUser
from app.common.response import Response
from app.dependencies import get_db
from app.llm import LLMClient, get_user_llm
from app.schemas.chat import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationPageResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageCreateRequest,
    MessageExchangeResponse,
    MessageResponse,
)
from app.schemas.skill import SkillMountRequest
from app.services import chat_service, skill_service

router = APIRouter(prefix="/conversations", tags=["对话相关的接口"])


@router.post(
    "",
    response_model=Response,
    summary="新建会话",
    description="创建一个空会话，标题缺省为「新会话」；返回会话ID与创建时间。",
)
def create_conversation(
    payload: ConversationCreateRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(
        data=ConversationResponse.model_validate(
            chat_service.create_conversation(db, user.id, payload)
        )
    )


@router.get(
    "",
    response_model=Response,
    summary="分页查询会话列表",
    description="按最后活动时间倒序返回会话，每项带该会话的消息条数。",
)
def list_conversations(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 10,
):
    page_data = chat_service.list_conversations(db, user.id, page=page, page_size=page_size)
    return Response.success(data=ConversationPageResponse.model_validate(page_data))


@router.get(
    "/{conversation_id}",
    response_model=Response,
    summary="查询会话详情",
    description="返回会话本身与该会话的全部消息，消息按发送顺序排列。",
)
def get_conversation(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    conversation = chat_service.get_conversation(db, user.id, conversation_id)
    data = {
        **ConversationResponse.model_validate(conversation).model_dump(),
        "messages": [MessageResponse.model_validate(m).model_dump() for m in conversation.messages],
    }
    return Response.success(data=ConversationDetailResponse.model_validate(data))


@router.patch(
    "/{conversation_id}",
    response_model=Response,
    summary="重命名会话",
    description="只修改标题。标题去首尾空白后不能为空，纯空白返回 400。",
)
def rename_conversation(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    payload: ConversationUpdateRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    conversation = chat_service.rename_conversation(db, user.id, conversation_id, payload)
    return Response.success(data=ConversationResponse.model_validate(conversation))


@router.put(
    "/{conversation_id}/skill",
    response_model=Response,
    summary="挂载或卸载技能",
    description="传 slug 挂上，传 null 卸载。会话或技能不存在都 404；技能挂了之后每次运行都会注入它的方法说明。",
)
def mount_skill(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    payload: SkillMountRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    conversation = skill_service.mount_skill(db, user.id, conversation_id, payload.slug)
    return Response.success(
        data={"conversation_id": conversation.id, "skill_slug": conversation.skill_slug}
    )


@router.delete(
    "/{conversation_id}",
    response_model=Response,
    summary="删除会话",
    description="删除会话及其全部消息（外键级联），删后无法恢复。",
)
def delete_conversation(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    chat_service.delete_conversation(db, user.id, conversation_id)
    return Response.success()


@router.post(
    "/{conversation_id}/messages",
    response_model=Response,
    summary="发送消息",
    description="写入用户消息并用最近 20 条上下文调用模型，同步返回用户消息与助手回复。",
)
def send_message(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    payload: MessageCreateRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMClient, Depends(get_user_llm)],
):
    user_message, assistant_message = chat_service.send_message(
        db, user.id, conversation_id, payload.content, llm
    )
    return Response.success(
        data=MessageExchangeResponse(
            user_message=MessageResponse.model_validate(user_message),
            assistant_message=MessageResponse.model_validate(assistant_message),
        )
    )


@router.post(
    "/{conversation_id}/messages/stream",
    summary="发送消息（流式）",
    description=(
        "写入用户消息并以 SSE 逐块返回助手回复。"
        "事件类型：meta（带 user_message）/ delta（增量文本）/ done（最终消息）/ error。"
    ),
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE 事件流",
        }
    },
)
def stream_message(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    payload: MessageCreateRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMClient, Depends(get_user_llm)],
):
    # 先同步做完校验与落库：这样 404/400 仍是普通 JSON，而不是流里的错误事件
    conversation, user_message, context, is_first = chat_service.prepare_stream(
        db, user.id, conversation_id, payload.content
    )
    events = chat_service.stream_reply(db, conversation, user_message, context, is_first, llm)
    return StreamingResponse(
        encode_sse(events),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
