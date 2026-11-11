"""MCP 工具市场接口：清单、接入、启停、删除、试连。

工具本身**不新接口**——接进来的工具会出现在 `GET /api/settings/tools` 里
（`source="mcp"`），开关与预算沿用阶段 6 的那套。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.common.response import Response
from app.dependencies import get_db
from app.schemas.mcp import McpServerCreateRequest, McpServerUpdateRequest
from app.services import mcp_service

router = APIRouter(prefix="/mcp", tags=["MCP 工具市场"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/catalog", response_model=Response, summary="内置市场清单")
def read_catalog(db: DbSession, user: CurrentUser):
    data = mcp_service.list_catalog(db, user.id)
    return Response.success(data=data.model_dump(mode="json"))


@router.get("/servers", response_model=Response, summary="已接入的 MCP 服务器")
def read_servers(db: DbSession, user: CurrentUser):
    data = mcp_service.list_servers(db, user.id)
    return Response.success(data=data.model_dump(mode="json"))


@router.post("/servers", response_model=Response, summary="接入一台 MCP 服务器")
def create_server(payload: McpServerCreateRequest, db: DbSession, user: CurrentUser):
    data = mcp_service.create_server(db, user.id, payload)
    return Response.success(data=data.model_dump(mode="json"))


@router.patch("/servers/{server_id}", response_model=Response, summary="修改/启停")
def update_server(
    server_id: int,
    payload: McpServerUpdateRequest,
    db: DbSession,
    user: CurrentUser,
):
    data = mcp_service.update_server(db, user.id, server_id, payload)
    return Response.success(data=data.model_dump(mode="json"))


@router.delete("/servers/{server_id}", response_model=Response, summary="移除服务器")
def delete_server(server_id: int, db: DbSession, user: CurrentUser):
    mcp_service.delete_server(db, user.id, server_id)
    return Response.success(data={"removed": True})


@router.post("/servers/{server_id}/test", response_model=Response, summary="试连并列工具")
def test_server(server_id: int, db: DbSession, user: CurrentUser):
    data = mcp_service.test_server(db, user.id, server_id)
    return Response.success(data=data.model_dump(mode="json"))
