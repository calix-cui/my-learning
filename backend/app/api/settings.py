"""设置接口：模型配置的读、写与连通性自测。

导出与注销放在账号侧（`/api/auth/me`、`/api/settings/export`），见 docs/setting design.md §五。
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.common.response import Response
from app.dependencies import get_db
from app.schemas.settings import (
    AppearanceSettingsUpdateRequest,
    ModelSettingsUpdateRequest,
    ModelTestRequest,
    ToolSettingsUpdateRequest,
)
from app.services import export_service, settings_service

router = APIRouter(prefix="/settings", tags=["设置相关的接口"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/model", response_model=Response, summary="读取当前用户的模型配置")
def read_model(db: DbSession, user: CurrentUser):
    data = settings_service.read_model_settings(db, user.id)
    return Response.success(data=data.model_dump(mode="json"))


@router.put("/model", response_model=Response, summary="保存当前用户的模型配置")
def update_model(payload: ModelSettingsUpdateRequest, db: DbSession, user: CurrentUser):
    data = settings_service.update_model_settings(db, user.id, payload)
    return Response.success(data=data.model_dump(mode="json"))


@router.post("/model/test", response_model=Response, summary="测试模型连通性（不落库）")
def test_model(payload: ModelTestRequest, db: DbSession, user: CurrentUser):
    data = settings_service.test_model_settings(db, user.id, payload)
    return Response.success(data=data.model_dump(mode="json"))


@router.get("/appearance", response_model=Response, summary="读取当前账号保存的外观")
def read_appearance(db: DbSession, user: CurrentUser):
    data = settings_service.read_appearance(db, user.id)
    return Response.success(data=data.model_dump(mode="json"))


@router.put("/appearance", response_model=Response, summary="保存外观（跨设备同步主题）")
def update_appearance(payload: AppearanceSettingsUpdateRequest, db: DbSession, user: CurrentUser):
    data = settings_service.update_appearance(db, user.id, payload)
    return Response.success(data=data.model_dump(mode="json"))


@router.get("/export", summary="导出当前用户的全部对话（json / markdown）")
def export_data(
    db: DbSession,
    user: CurrentUser,
    format: Annotated[str, Query(pattern="^(json|markdown)$")] = "json",
):
    if format == "markdown":
        chunks: Iterator[str] = export_service.export_markdown(db, user)
        filename = "my-agent-conversations.md"
        media_type = "text/markdown; charset=utf-8"
    else:
        chunks = export_service.export_json(db, user)
        filename = "my-agent-conversations.json"
        media_type = "application/json; charset=utf-8"

    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]


@router.get("/tools", response_model=Response, summary="工具清单与今日用量")
def read_tools(db: DbSession, user: CurrentUser):
    data = settings_service.read_tool_settings(db, user.id)
    return Response.success(data=data.model_dump(mode="json"))


@router.put("/tools", response_model=Response, summary="批量启停工具、调整每日上限")
def update_tools(payload: ToolSettingsUpdateRequest, db: DbSession, user: CurrentUser):
    data = settings_service.update_tool_settings(db, user.id, payload)
    return Response.success(data=data.model_dump(mode="json"))


@router.get("/tools/stats", response_model=Response, summary="最近 N 天的工具调用统计")
def read_tool_stats(
    db: DbSession,
    user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=30, description="回溯天数")] = 7,
):
    data = settings_service.read_tool_stats(db, user.id, days=days)
    return Response.success(data=data.model_dump(mode="json"))
