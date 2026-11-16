"""Skill resource allowlist, bounded IO and symlink rejection."""

import os

import pytest

from app.skills.resources import (
    MAX_RESOURCE_BYTES,
    SkillResourceError,
    list_resources,
    read_resource,
)


@pytest.fixture
def package(tmp_path):
    root = tmp_path.resolve() / "skill"
    (root / "references").mkdir(parents=True)
    (root / "references" / "guide.md").write_text("参考资料", encoding="utf-8")
    return root


def test_lists_names_and_reads_text(package):
    assert list_resources(package) == ("references/guide.md",)
    assert read_resource(package, "references/guide.md") == "参考资料"


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../private.txt",
        "references/../private.txt",
        "references\\guide.md",
        "references//guide.md",
        "scripts/run.py",
        "references/x.exe",
        "references/a/b/c/d.md",
        "references/./guide.md",
        "references/\x00.md",
    ],
)
def test_rejects_unsafe_paths(package, path):
    with pytest.raises(SkillResourceError):
        read_resource(package, path)


@pytest.mark.parametrize("data", [b"x" * (MAX_RESOURCE_BYTES + 1), b"\xff", b"hello\x00world"])
def test_rejects_large_binary_and_invalid_utf8(package, data):
    (package / "references" / "bad.txt").write_bytes(data)
    with pytest.raises(SkillResourceError):
        read_resource(package, "references/bad.txt")


def test_rejects_symlink_file_and_directory_even_after_listing(package):
    assert "references/guide.md" in list_resources(package)
    target = package.parent / "secret.txt"
    target.write_text("SECRET", encoding="utf-8")
    (package / "references" / "guide.md").unlink()
    (package / "references" / "guide.md").symlink_to(target)
    with pytest.raises(SkillResourceError):
        read_resource(package, "references/guide.md")
    (package / "assets").symlink_to(package / "references", target_is_directory=True)
    with pytest.raises(SkillResourceError):
        read_resource(package, "assets/guide.md")
    assert list_resources(package) == ()


def test_rejects_fifo_without_blocking(package):
    os.mkfifo(package / "references" / "pipe.txt")
    with pytest.raises(SkillResourceError):
        read_resource(package, "references/pipe.txt")


def test_resource_listing_is_bounded(package):
    for index in range(100):
        (package / "references" / f"{index}.md").touch()
    assert len(list_resources(package)) == 64
