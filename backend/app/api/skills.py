"""技能接口：读取本地目录，以及会话级挂载（挂载在会话路由上）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.common.exceptions import BusinessError
from app.common.response import Response
from app.dependencies import get_db
from app.schemas.skill import SkillCatalogResponse
from app.services import skill_catalog_service

router = APIRouter(prefix="/skills", tags=["Skill"])


@router.get("/catalog", response_model=Response, summary="本地 Skill 目录")
def read_catalog(user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    data = skill_catalog_service.catalog_response(db, user.id)
    db.commit()
    return Response.success(data=SkillCatalogResponse.model_validate(data))


@router.post("/catalog/rescan", response_model=Response, summary="重新扫描本地 Skill")
def rescan_catalog(user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    data = skill_catalog_service.catalog_response(db, user.id, rescan=True)
    db.commit()
    return Response.success(data=SkillCatalogResponse.model_validate(data))


@router.get("/catalog/detail", response_model=Response, summary="读取本地 Skill")
def read_catalog_detail(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    key: Annotated[str, Query(min_length=1, max_length=128)],
    version: str | None = None,
):
    snapshot = skill_catalog_service.catalog_snapshot(db, user.id)
    if version is not None and version != snapshot["version"]:
        raise BusinessError("Skill 目录已更新，请重新扫描后查看", code=409)
    registry = skill_catalog_service.registry_from_snapshot(user.id, snapshot)
    try:
        loaded = registry.load(key)
    except ValueError as exc:
        raise BusinessError("Skill 文件已变化，请重新扫描", code=409) from exc
    if loaded is None:
        raise BusinessError("Skill 不存在或当前无法读取", code=404)
    return Response.success(data={"key": key, "instructions": loaded.instructions})
