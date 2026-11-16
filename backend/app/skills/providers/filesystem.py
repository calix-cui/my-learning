"""Repository-bundled Skill source. Discovery returns metadata; load reads the body on demand."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.skills.loader import (
    MAX_SKILL_FILE_BYTES,
    SKILL_FILE,
    SKILLS_DIR,
    SkillFormatError,
    parse_skill,
    parse_skill_metadata,
)
from app.skills.models import LoadedSkill, SkillDescriptor
from app.skills.resources import SkillResourceError, list_resources, read_resource

logger = logging.getLogger(__name__)


class FileSystemSkillProvider:
    """Discovers repository Skill packages each time a run builds its catalog."""

    source = "builtin"
    trust = "trusted"

    def __init__(self, directory: Path | None = None) -> None:
        self._root = (directory or SKILLS_DIR).resolve()
        self._paths: dict[str, Path] = {}

    def discover(self) -> list[SkillDescriptor]:
        descriptors: list[SkillDescriptor] = []
        paths: dict[str, Path] = {}
        if not self._root.is_dir():
            self._paths = paths
            return descriptors

        seen_slugs: set[str] = set()
        for path in sorted(self._root.glob(f"*/{SKILL_FILE}")):
            try:
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(self._root):
                    raise SkillFormatError("Skill 文件不能指向根目录之外")
                if resolved.stat().st_size > MAX_SKILL_FILE_BYTES:
                    raise SkillFormatError("Skill 文件超过大小限制")
                raw = resolved.read_text(encoding="utf-8")
                summary = parse_skill_metadata(
                    raw, origin=str(resolved), default_slug=resolved.parent.name
                )
                if summary.slug in seen_slugs:
                    logger.warning("忽略重复的内置 Skill 标识：%s", summary.slug)
                    continue
                seen_slugs.add(summary.slug)
                content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                key = f"builtin:{summary.slug}"
                descriptors.append(
                    SkillDescriptor(
                        key=key,
                        slug=summary.slug,
                        name=summary.name,
                        description=summary.description,
                        source=self.source,
                        trust=self.trust,
                        version=content_hash,
                        tools=summary.tools,
                        icon=summary.icon,
                    )
                )
                paths[key] = resolved
            except (OSError, UnicodeError, SkillFormatError) as exc:
                logger.warning("忽略不可用的内置 Skill %s：%s", path, exc)

        self._paths = paths
        return descriptors

    def load(self, key: str) -> LoadedSkill | None:
        path = self._paths.get(key)
        if path is None:
            return None
        try:
            if not path.resolve(strict=True).is_relative_to(self._root):
                raise SkillFormatError("Skill 文件不能指向根目录之外")
            if path.stat().st_size > MAX_SKILL_FILE_BYTES:
                raise SkillFormatError("Skill 文件超过大小限制")
            raw = path.read_text(encoding="utf-8")
            skill = parse_skill(raw, origin=str(path), default_slug=path.parent.name)
        except (OSError, UnicodeError, SkillFormatError) as exc:
            logger.warning("无法加载内置 Skill %s：%s", key, exc)
            return None

        content_hash = hashlib.sha256(skill.instructions.encode("utf-8")).hexdigest()
        descriptor = SkillDescriptor(
            key=key,
            slug=skill.slug,
            name=skill.name,
            description=skill.description,
            source=skill.source,
            trust=self.trust,
            version=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            tools=skill.tools,
            icon=skill.icon,
        )
        return LoadedSkill(
            descriptor=descriptor,
            instructions=skill.instructions,
            content_hash=content_hash,
            resources=list_resources(path.parent),
        )

    def read_resource(self, key: str, path: str) -> str:
        skill_path = self._paths.get(key)
        if skill_path is None:
            raise SkillResourceError("Skill 不在当前目录中")
        return read_resource(skill_path.parent, path)
