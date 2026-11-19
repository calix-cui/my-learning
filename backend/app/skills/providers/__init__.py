"""Skill catalog providers used by the per-request registry."""

from app.skills.providers.filesystem import FileSystemSkillProvider

__all__ = ["FileSystemSkillProvider"]
