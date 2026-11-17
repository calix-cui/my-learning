"""技能接口：列表、增删改，以及会话级挂载。"""

from io import BytesIO
from typing import Annotated
from zipfile import ZipFile

import yaml
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response as FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.common.exceptions import BusinessError
from app.common.response import Response
from app.dependencies import get_db
from app.models import Skill as SkillRow
from app.schemas.skill import (
    SkillCatalogResponse,
    SkillCreateRequest,
    SkillDetail,
    SkillItem,
    SkillListResponse,
    SkillUpdateRequest,
)
from app.services import chat_service, skill_catalog_service, skill_service
from app.skills.models import SKILL_SLUG_PATTERN

router = APIRouter(prefix="/skills", tags=["Skill"])


def _item(skill, *, mounted: str | None) -> SkillItem:
    return SkillItem(
        slug=skill.slug,
        name=skill.name,
        description=skill.description,
        tools=list(skill.tools),
        tool_count=skill.tool_count,
        icon=skill.icon,
        source=skill.source,
        skill_id=skill.skill_id,
        mounted=skill.slug == mounted,
    )


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


@router.get("/legacy/export", summary="导出旧版数据库 Skill")
def export_legacy(user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    output = BytesIO()
    rows = db.scalars(select(SkillRow).where(SkillRow.user_id == user.id).order_by(SkillRow.id))
    with ZipFile(output, "w") as archive:
        for row in rows:
            if not SKILL_SLUG_PATTERN.fullmatch(row.slug):
                raise BusinessError("旧 Skill 标识异常，请检查记录后导出")
            frontmatter = yaml.safe_dump(
                {
                    "slug": row.slug,
                    "name": row.name,
                    "description": row.description,
                    "tools": row.tools or [],
                    "icon": row.icon,
                },
                allow_unicode=True,
            )
            archive.writestr(
                f"{row.slug}/SKILL.md", f"---\n{frontmatter}---\n\n{row.instructions}\n"
            )
    return FileResponse(
        content=output.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="legacy-skills.zip"'},
    )


@router.get(
    "",
    response_model=Response,
    summary="技能列表",
    description="内置技能 + 自定义技能。传 conversation_id 时顺带标出该会话挂载了哪个。",
)
def list_skills(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    conversation_id: Annotated[int | None, Query(description="会话ID，用于标出挂载状态")] = None,
):
    mounted = None
    if conversation_id is not None:
        conversation = chat_service.get_conversation(db, user.id, conversation_id)
        mounted = conversation.skill_slug

    items = [_item(skill, mounted=mounted) for skill in skill_service.list_skills(db, user.id)]
    return Response.success(data=SkillListResponse(items=items, mounted=mounted))


@router.get(
    "/{slug}",
    response_model=Response,
    summary="技能详情",
    description="带 Markdown 正文，用于设置页编辑与「查看说明」。",
)
def get_skill(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    slug: Annotated[str, Path(description="技能标识")],
):
    skill = skill_service.get_skill(db, user.id, slug)
    if skill is None:
        raise BusinessError("技能不存在", code=404)
    return Response.success(
        data=SkillDetail(
            **_item(skill, mounted=None).model_dump(),
            instructions=skill.instructions,
        )
    )


@router.post(
    "",
    response_model=Response,
    summary="新建自定义 Skill（旧版）",
    deprecated=True,
    description="内置技能只读，标识撞了内置或已有自定义都会 400。",
)
def create_skill(
    payload: SkillCreateRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    skill = skill_service.create_skill(
        db,
        user.id,
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        instructions=payload.instructions,
        tools=payload.tools,
        icon=payload.icon,
    )
    return Response.success(data=_item(skill, mounted=None))


@router.patch(
    "/{skill_id}",
    response_model=Response,
    summary="修改自定义 Skill（旧版）",
    deprecated=True,
    description="只传要改的字段。内置技能不在表里，编辑它一律 404。",
)
def update_skill(
    payload: SkillUpdateRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    skill_id: Annotated[int, Path(description="技能主键")],
):
    skill = skill_service.update_skill(
        db,
        user.id,
        skill_id,
        name=payload.name,
        description=payload.description,
        instructions=payload.instructions,
        tools=payload.tools,
        icon=payload.icon,
    )
    return Response.success(data=_item(skill, mounted=None))


@router.delete(
    "/{skill_id}",
    response_model=Response,
    summary="删除自定义 Skill（旧版）",
    deprecated=True,
    description="正在使用它的会话会回落到「不挂技能」，不做级联删除。",
)
def delete_skill(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    skill_id: Annotated[int, Path(description="技能主键")],
):
    skill_service.delete_skill(db, user.id, skill_id)
    return Response.success(data={"deleted": skill_id})
