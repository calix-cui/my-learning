"""Bounded text resources; all path components are opened without following symlinks."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath

MAX_RESOURCE_BYTES = 16_384
MAX_RESOURCE_PATHS = 64
MAX_RESOURCE_DEPTH = 4
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}


class SkillResourceError(ValueError):
    pass


def resource_parts(path: str) -> tuple[str, ...]:
    parts = path.split("/")
    if (
        not path
        or len(path) > 240
        or "\\" in path
        or any(ord(char) < 32 for char in path)
        or any(part in {"", ".", ".."} for part in parts)
        or len(parts) < 2
        or len(parts) > MAX_RESOURCE_DEPTH
        or parts[0] not in {"references", "assets"}
        or PurePosixPath(path).suffix.lower() not in TEXT_SUFFIXES
    ):
        raise SkillResourceError("资源路径或文件类型不受支持")
    return tuple(parts)


def list_resources(root: Path) -> tuple[str, ...]:
    """List names only. Never read bodies during discovery; cap traversal work."""
    result: list[str] = []
    visited = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        visited += 1
        if visited > 256:
            break
        relative = Path(current).relative_to(root)
        depth = len(relative.parts)
        dirs[:] = sorted(
            name
            for name in dirs
            if not (Path(current) / name).is_symlink()
            and (depth != 0 or name in {"references", "assets"})
            and depth < MAX_RESOURCE_DEPTH - 1
        )[: max(0, 256 - visited)]
        for name in sorted(files):
            visited += 1
            if visited > 256:
                return tuple(result)
            path = (relative / name).as_posix()
            try:
                resource_parts(path)
                if (Path(current) / name).is_file() and not (Path(current) / name).is_symlink():
                    result.append(path)
            except SkillResourceError:
                continue
            if len(result) >= MAX_RESOURCE_PATHS:
                return tuple(result)
    return tuple(result)


def read_resource(root: Path, path: str) -> str:
    return read_package_text(root, resource_parts(path), MAX_RESOURCE_BYTES)


def read_package_text(root: Path, parts: tuple[str, ...], max_bytes: int) -> str:
    """以目录描述符固定路径，拒绝链接、特殊文件和超限 UTF-8 内容。"""
    if not parts or any(part in {"", ".", ".."} or "/" in part or "\\" in part for part in parts):
        raise SkillResourceError("文件路径不合法")
    # Fail closed on platforms without safe descriptor-relative file access.
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise SkillResourceError("当前平台暂不支持安全资源读取")
    descriptors: list[int] = []
    try:
        # Pin every directory starting at the filesystem root, including the package root.
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(root.anchor, directory_flags)
        descriptors.append(fd)
        for component in (*root.parts[1:], *parts[:-1]):
            fd = os.open(component, directory_flags, dir_fd=fd)
            descriptors.append(fd)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        descriptors.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
            raise SkillResourceError("文件必须是大小受限的普通文本文件")
        raw = bytearray()
        while len(raw) <= max_bytes:
            chunk = os.read(fd, min(4096, max_bytes + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > max_bytes:
            raise SkillResourceError("资源超过大小限制")
        content = raw.decode("utf-8")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in content):
            raise SkillResourceError("资源不是可读取的 UTF-8 文本")
        return content
    except (OSError, UnicodeError) as exc:
        raise SkillResourceError("资源不可读取或不是 UTF-8 文本") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
