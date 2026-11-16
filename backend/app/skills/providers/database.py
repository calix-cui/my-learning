"""User-owned Skill source. Discovery selects metadata columns only."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Skill as SkillRow
from app.skills.models import SOURCE_CUSTOM, LoadedSkill, SkillDescriptor
from app.skills.resources import SkillResourceError


class DatabaseSkillProvider:
    """A user-scoped view of custom Skill rows."""

    source = SOURCE_CUSTOM
    trust = "user_authored"

    def __init__(self, db: Session, user_id: int) -> None:
        self._db = db
        self._user_id = user_id

    def discover(self) -> list[SkillDescriptor]:
        rows = self._db.execute(
            select(
                SkillRow.id,
                SkillRow.slug,
                SkillRow.name,
                SkillRow.description,
                SkillRow.tools,
                SkillRow.icon,
                SkillRow.update_time,
            )
            .where(SkillRow.user_id == self._user_id)
            .order_by(SkillRow.id)
        )
        return [
            SkillDescriptor(
                key=f"user:{self._user_id}:skill:{row.id}",
                slug=row.slug,
                name=row.name,
                description=row.description,
                source=self.source,
                trust=self.trust,
                version=row.update_time.isoformat(),
                tools=tuple(row.tools or ()),
                icon=row.icon,
                skill_id=row.id,
            )
            for row in rows
        ]

    def load(self, key: str) -> LoadedSkill | None:
        prefix = f"user:{self._user_id}:skill:"
        if not key.startswith(prefix):
            return None
        try:
            skill_id = int(key[len(prefix) :])
        except ValueError:
            return None
        row = self._db.scalar(
            select(SkillRow).where(SkillRow.id == skill_id, SkillRow.user_id == self._user_id)
        )
        if row is None:
            return None
        instructions = row.instructions
        descriptor = SkillDescriptor(
            key=key,
            slug=row.slug,
            name=row.name,
            description=row.description,
            source=self.source,
            trust=self.trust,
            version=row.update_time.isoformat(),
            tools=tuple(row.tools or ()),
            icon=row.icon,
            skill_id=row.id,
        )
        return LoadedSkill(
            descriptor=descriptor,
            instructions=instructions,
            content_hash=hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
        )

    def read_resource(self, _key: str, _path: str) -> str:
        raise SkillResourceError("自建 Skill 尚不支持文件资源")
