"""从配置的本地根目录发现 Skill，按需读取正文。"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import asdict
from itertools import islice
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
from app.skills.resources import (
    SkillResourceError,
    list_resources,
    read_package_text,
    read_resource,
)

logger = logging.getLogger(__name__)


class FileSystemSkillProvider:
    """目录扫描和正文读取共用安全文件访问，缓存清单可跨请求恢复。"""

    source = "builtin"
    trust = "trusted"

    def __init__(
        self,
        directory: Path | None = None,
        *,
        namespace: str = "builtin",
        source: str = "builtin",
        manifest: list[dict] | None = None,
    ) -> None:
        self._root = (directory or SKILLS_DIR).absolute()
        self.namespace = namespace
        self.source = source
        self.trust = "trusted" if source == "builtin" else "untrusted"
        self._paths: dict[str, Path] = {}
        self._cached: list[SkillDescriptor] | None = None
        if manifest is not None:
            self._cached = []
            for item in manifest:
                descriptor = SkillDescriptor(
                    **{**item["descriptor"], "tools": tuple(item["descriptor"]["tools"])}
                )
                package = item["package"]
                if (
                    not isinstance(package, str)
                    or Path(package).name != package
                    or package in {".", ".."}
                    or "\\" in package
                ):
                    continue
                self._paths[descriptor.key] = self._root / package / SKILL_FILE
                self._cached.append(descriptor)

    def discover(self) -> list[SkillDescriptor]:
        if self._cached is not None:
            return list(self._cached)
        descriptors: list[SkillDescriptor] = []
        paths: dict[str, Path] = {}
        try:
            if self._root.is_symlink():
                raise SkillFormatError("Skill 根目录不能是符号链接")
            with os.scandir(self._root) as entries:
                packages = sorted(
                    item.name for item in islice(entries, 256) if item.is_dir(follow_symlinks=False)
                )
        except FileNotFoundError:
            packages = []
        except (OSError, SkillFormatError) as exc:
            raise SkillFormatError("Skill 根目录无法扫描，请检查目录配置") from exc

        seen_slugs: set[str] = set()
        for package in packages:
            path = self._root / package / SKILL_FILE
            if len(descriptors) >= 100:
                logger.warning("Skill 数量达到当前目录上限")
                break
            try:
                raw = read_package_text(self._root, (package, SKILL_FILE), MAX_SKILL_FILE_BYTES)
                summary = parse_skill_metadata(raw, origin=str(path), default_slug=package)
                if summary.slug in seen_slugs:
                    logger.warning("忽略重复的 Skill 标识：%s", summary.slug)
                    continue
                seen_slugs.add(summary.slug)
                key = f"{self.namespace}:{summary.slug}"
                descriptors.append(
                    SkillDescriptor(
                        key=key,
                        slug=summary.slug,
                        name=summary.name,
                        description=summary.description,
                        source=self.source,
                        trust=self.trust,
                        version=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                        tools=summary.tools,
                        icon=summary.icon,
                    )
                )
                paths[key] = path
            except (OSError, UnicodeError, SkillFormatError, SkillResourceError) as exc:
                logger.warning("忽略不可用的 Skill %s：%s", path, exc)

        self._paths = paths
        self._cached = descriptors
        return list(descriptors)

    def manifest(self) -> list[dict]:
        return [
            {"descriptor": asdict(item), "package": self._paths[item.key].parent.name}
            for item in self.discover()
        ]

    def load(self, key: str) -> LoadedSkill | None:
        path = self._paths.get(key)
        if path is None:
            return None
        try:
            raw = read_package_text(
                self._root, (path.parent.name, SKILL_FILE), MAX_SKILL_FILE_BYTES
            )
            skill = parse_skill(raw, origin=str(path), default_slug=path.parent.name)
        except (OSError, UnicodeError, SkillFormatError, SkillResourceError) as exc:
            logger.warning("无法加载 Skill %s：%s", key, exc)
            return None

        content_hash = hashlib.sha256(skill.instructions.encode("utf-8")).hexdigest()
        descriptor = SkillDescriptor(
            key=key,
            slug=skill.slug,
            name=skill.name,
            description=skill.description,
            source=self.source,
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
