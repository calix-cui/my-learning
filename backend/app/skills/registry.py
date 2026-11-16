"""Per-request Skill catalog with stable keys and explicit source precedence."""

from __future__ import annotations

from typing import Protocol

from app.skills.models import LoadedSkill, SkillDescriptor
from app.skills.resources import SkillResourceError


class SkillProvider(Protocol):
    def discover(self) -> list[SkillDescriptor]: ...

    def load(self, key: str) -> LoadedSkill | None: ...

    def read_resource(self, key: str, path: str) -> str: ...


class SkillRegistry:
    """Combines providers in priority order; earlier providers shadow duplicate slugs."""

    def __init__(self, providers: list[SkillProvider]) -> None:
        self._providers = providers
        self._by_key: dict[str, tuple[SkillDescriptor, SkillProvider]] = {}

    def discover(self) -> list[SkillDescriptor]:
        by_slug: dict[str, SkillDescriptor] = {}
        by_key: dict[str, tuple[SkillDescriptor, SkillProvider]] = {}
        for provider in self._providers:
            for descriptor in provider.discover():
                if descriptor.key in by_key:
                    raise ValueError(f"Skill key 重复：{descriptor.key}")
                if descriptor.slug in by_slug:
                    continue
                by_slug[descriptor.slug] = descriptor
                by_key[descriptor.key] = (descriptor, provider)
        self._by_key = by_key
        return list(by_slug.values())

    def load(self, key: str) -> LoadedSkill | None:
        if not self._by_key:
            self.discover()
        entry = self._by_key.get(key)
        if entry is None:
            return None
        expected, provider = entry
        loaded = provider.load(key)
        if loaded is None:
            return None
        actual = loaded.descriptor
        if (
            actual.key != expected.key
            or actual.slug != expected.slug
            or actual.version != expected.version
        ):
            raise ValueError("Skill Provider 返回了与目录项不匹配的内容")
        return loaded

    def read_resource(self, loaded: LoadedSkill, path: str) -> str:
        if path not in loaded.resources:
            raise SkillResourceError("资源不在已加载 Skill 的清单中")
        if not self._by_key:
            self.discover()
        entry = self._by_key.get(loaded.descriptor.key)
        if entry is None or entry[0].version != loaded.descriptor.version:
            raise SkillResourceError("Skill 已更新或不可用，请重新发起任务")
        return entry[1].read_resource(loaded.descriptor.key, path)

    def get_by_slug(self, slug: str) -> LoadedSkill | None:
        descriptor = next((item for item in self.discover() if item.slug == slug), None)
        return self.load(descriptor.key) if descriptor is not None else None

    def contains_slug(self, slug: str) -> bool:
        return any(item.slug == slug for item in self.discover())


__all__ = ["SkillProvider", "SkillRegistry"]
