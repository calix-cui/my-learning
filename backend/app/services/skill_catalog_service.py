"""账号级本地 Skill 目录；共享数据库元数据，正文按运行加载。"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.dev_trace import trace
from app.common.exceptions import BusinessError
from app.config import settings
from app.models import UserSettings
from app.skills.loader import SKILLS_DIR, SkillFormatError
from app.skills.providers.filesystem import FileSystemSkillProvider
from app.skills.registry import SkillRegistry

MAX_CATALOG_ITEMS = 100


def configured_roots(user_id: int) -> list[tuple[str, str, Path]]:
    roots = [("builtin", "builtin", SKILLS_DIR)]
    roots.extend(
        (f"shared-{index}", "local", directory)
        for index, directory in enumerate(settings.skill_shared_dirs[:8])
    )
    roots.append(("user", "local", settings.skill_user_root / str(user_id)))
    return roots


def _signature(user_id: int) -> str:
    roots = [(namespace, str(path.absolute())) for namespace, _, path in configured_roots(user_id)]
    return hashlib.sha256(json.dumps(roots).encode()).hexdigest()


def registry_from_snapshot(user_id: int, snapshot: dict) -> SkillRegistry:
    if snapshot.get("roots") != _signature(user_id):
        raise BusinessError("Skill 目录配置已变化，请在设置中重新扫描", code=409)
    manifests = snapshot["providers"]
    providers = [
        FileSystemSkillProvider(
            root, namespace=namespace, source=source, manifest=manifests.get(namespace, [])
        )
        for namespace, source, root in configured_roots(user_id)
    ]
    return SkillRegistry(providers, preserve_sources=True)


def catalog_snapshot(db: Session, user_id: int, *, rescan: bool = False) -> dict:
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if row and row.skill_catalog and not rescan:
        if row.skill_catalog.get("roots") != _signature(user_id):
            raise BusinessError("Skill 目录配置已变化，请在设置中重新扫描", code=409)
        return row.skill_catalog

    providers: dict[str, list[dict]] = {}
    remaining = MAX_CATALOG_ITEMS
    try:
        for namespace, source, root in configured_roots(user_id):
            provider = FileSystemSkillProvider(root, namespace=namespace, source=source)
            providers[namespace] = provider.manifest()[:remaining]
            remaining -= len(providers[namespace])
    except SkillFormatError as exc:
        raise BusinessError(str(exc)) from exc
    snapshot = {"roots": _signature(user_id), "providers": providers}
    version = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    snapshot["version"] = version
    if row is None:
        # 并发的账号初始化只插入一行设置，保留其他请求已写入的字段。
        try:
            with db.begin_nested():
                row = UserSettings(user_id=user_id)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    row.skill_catalog = snapshot
    db.flush()
    trace("skill.catalog.scan", count=MAX_CATALOG_ITEMS - remaining, version=version)
    return snapshot


def catalog_response(db: Session, user_id: int, *, rescan: bool = False) -> dict:
    snapshot = catalog_snapshot(db, user_id, rescan=rescan)
    registry = registry_from_snapshot(user_id, snapshot)
    return {
        "items": [asdict(item) for item in registry.discover()],
        "version": snapshot["version"],
        "legacy_count": legacy_count(db, user_id),
    }


def legacy_count(db: Session, user_id: int) -> int:
    from sqlalchemy import func

    from app.models import Skill

    return db.scalar(select(func.count(Skill.id)).where(Skill.user_id == user_id)) or 0
