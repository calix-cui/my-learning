from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.dependencies import get_db
from app.schemas.chat import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationPageResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageResponse,
)
from app.services import chat_service

router = APIRouter(prefix="/conversations", tags=["对话相关的接口"])


@router.post(
    "",
    response_model=Response,
    summary="新建会话",
    description="创建一个空会话，标题缺省为「新会话」；返回会话ID与创建时间。",
)
def create_conversation(
    payload: ConversationCreateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(
        data=ConversationResponse.model_validate(chat_service.create_conversation(db, payload))
    )


@router.get(
    "",
    response_model=Response,
    summary="分页查询会话列表",
    description="按最后活动时间倒序返回会话，每项带该会话的消息条数。",
)
def list_conversations(
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 10,
):
    page_data = chat_service.list_conversations(db, page=page, page_size=page_size)
    return Response.success(data=ConversationPageResponse.model_validate(page_data))


@router.get(
    "/{conversation_id}",
    response_model=Response,
    summary="查询会话详情",
    description="返回会话本身与该会话的全部消息，消息按发送顺序排列。",
)
def get_conversation(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    db: Annotated[Session, Depends(get_db)],
):
    conversation = chat_service.get_conversation(db, conversation_id)
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
    db: Annotated[Session, Depends(get_db)],
):
    conversation = chat_service.rename_conversation(db, conversation_id, payload)
    return Response.success(data=ConversationResponse.model_validate(conversation))


@router.delete(
    "/{conversation_id}",
    response_model=Response,
    summary="删除会话",
    description="删除会话及其全部消息（外键级联），删后无法恢复。",
)
def delete_conversation(
    conversation_id: Annotated[int, Path(gt=0, description="会话ID")],
    db: Annotated[Session, Depends(get_db)],
):
    chat_service.delete_conversation(db, conversation_id)
    return Response.success()
