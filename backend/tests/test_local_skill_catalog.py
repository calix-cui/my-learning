"""本地 Skill 发现、单条选择、渐进加载与账号隔离。"""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.llm import get_user_llm
from app.llm.fake import FakeLLM, final_reply, tool_reply
from app.main import app
from app.models import AgentRun
from app.services import skill_catalog_service

LOAD_SKILL = "__runtime_request_skill_load"


def package(root: Path, slug="guide", body="LOCAL_PRIVATE_INSTRUCTIONS", **extra) -> Path:
    directory = root / slug
    directory.mkdir(parents=True, exist_ok=True)
    import yaml

    metadata = {"name": slug, "description": "完成该任务时使用", **extra}
    file = directory / "SKILL.md"
    file.write_text(f"""---
{yaml.safe_dump(metadata, allow_unicode=True)}---

{body}""")
    return file


@pytest.fixture
def roots(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    shared = root / "shared"
    private = root / "users"
    shared.mkdir()
    monkeypatch.setattr(settings, "skill_shared_dirs", [shared])
    monkeypatch.setattr(settings, "skill_user_root", private)
    return shared, private


def events(response):
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]


def send(client: TestClient, conversation_id: int, **kwargs):
    return events(
        client.post(
            f"/api/conversations/{conversation_id}/messages/stream",
            json={"execution": "auto", "content": "按指引处理", **kwargs},
        )
    )


def test_account_catalog_reads_files_and_rescans(client, roots):
    shared, private = roots
    user_id = client.get("/api/auth/me").json()["data"]["id"]
    package(shared)
    package(private / str(user_id), "private")
    first = client.post("/api/skills/catalog/rescan").json()["data"]
    keys = [item["key"] for item in first["items"]]
    assert {"shared-0:guide", "user:private"} <= set(keys)
    assert "LOCAL_PRIVATE_INSTRUCTIONS" not in json.dumps(first)
    package(shared, "new")
    assert client.get("/api/skills/catalog").json()["data"] == first
    refreshed = client.post("/api/skills/catalog/rescan").json()["data"]
    assert refreshed["version"] != first["version"]
    assert "shared-0:new" in [item["key"] for item in refreshed["items"]]
    detail = client.get(
        "/api/skills/catalog/detail",
        params={"key": "shared-0:new", "version": refreshed["version"]},
    )
    assert detail.json()["data"]["instructions"] == "LOCAL_PRIVATE_INSTRUCTIONS"


def test_catalog_is_account_scoped(client, anon_client, roots):
    _, private = roots
    user_id = client.get("/api/auth/me").json()["data"]["id"]
    package(private / str(user_id), "private")
    assert anon_client.get("/api/skills/catalog").status_code == 401
    assert anon_client.post("/api/skills/catalog/rescan").status_code == 401
    anon_client.post(
        "/api/auth/register", json={"email": "other-catalog@example.com", "password": "password123"}
    )
    foreign = anon_client.post("/api/skills/catalog/rescan").json()["data"]
    assert "user:private" not in [item["key"] for item in foreign["items"]]
    assert (
        anon_client.get("/api/skills/catalog/detail", params={"key": "user:private"}).status_code
        == 404
    )


def test_explicit_skill_only_applies_to_current_message_and_chat_does_not_scan(
    client, db_session, roots, monkeypatch
):
    shared, _ = roots
    package(shared)
    catalog = client.post("/api/skills/catalog/rescan").json()["data"]
    conversation = client.post("/api/conversations", json={}).json()["data"]["id"]
    fake = FakeLLM(tool_script=[final_reply("第一条"), final_reply("第二条")])
    app.dependency_overrides[get_user_llm] = lambda: fake
    original = os.scandir

    def no_scan(path):
        assert Path(path) != shared
        return original(path)

    monkeypatch.setattr(os, "scandir", no_scan)
    try:
        first = send(
            client,
            conversation,
            skill_keys=["shared-0:guide"],
            skill_mode="manual",
            skill_catalog_version=catalog["version"],
        )
        second = send(client, conversation, skill_keys=[], skill_mode="manual")
        assert "skill_loaded" in [item["type"] for item in first]
        assert "LOCAL_PRIVATE_INSTRUCTIONS" in json.dumps(fake.tool_calls_seen[0])
        assert "LOCAL_PRIVATE_INSTRUCTIONS" not in json.dumps(fake.tool_calls_seen[1])
        assert "skill_loaded" not in [item["type"] for item in second]
        run = db_session.get(AgentRun, first[0]["run_id"])
        assert run.skill_snapshot["loaded"][0]["instructions"] == "LOCAL_PRIVATE_INSTRUCTIONS"
        assert "filesystem_catalog" in run.skill_snapshot
    finally:
        app.dependency_overrides.pop(get_user_llm, None)


def test_model_sees_metadata_and_loads_skill_and_text_resource_on_demand(client, roots):
    shared, _ = roots
    file = package(shared)
    (file.parent / "references").mkdir()
    (file.parent / "references" / "check.md").write_text("CHECKLIST_PRIVATE")
    client.post("/api/skills/catalog/rescan")
    fake = FakeLLM(
        tool_script=[
            tool_reply(LOAD_SKILL, {"skill_key": "shared-0:guide"}),
            tool_reply(LOAD_SKILL, {"skill_key": "shared-0:guide"}),
            tool_reply(
                "__runtime_read_skill_resource",
                {"skill_key": "shared-0:guide", "path": "references/check.md"},
            ),
            final_reply("按指引完成"),
        ]
    )
    app.dependency_overrides[get_user_llm] = lambda: fake
    try:
        conversation = client.post("/api/conversations", json={}).json()["data"]["id"]
        output = send(client, conversation, skill_mode="auto")
        first = json.dumps(fake.tool_calls_seen[0], ensure_ascii=False)
        assert "完成该任务时使用" in first
        assert "LOCAL_PRIVATE_INSTRUCTIONS" not in first
        assert "CHECKLIST_PRIVATE" not in first
        assert "LOCAL_PRIVATE_INSTRUCTIONS" in json.dumps(fake.tool_calls_seen[1])
        assert "CHECKLIST_PRIVATE" in json.dumps(fake.tool_calls_seen[-1])
        assert len([item for item in output if item["type"] == "skill_loaded"]) == 1
        assert output[-1]["type"] == "run_finished"
    finally:
        app.dependency_overrides.pop(get_user_llm, None)


def test_explicit_unknown_key_or_stale_catalog_rejected_before_run_creation(client, roots):
    shared, _ = roots
    package(shared)
    before = client.post("/api/skills/catalog/rescan").json()["data"]
    conversation = client.post("/api/conversations", json={}).json()["data"]["id"]
    response = client.post(
        f"/api/conversations/{conversation}/messages/stream",
        json={
            "execution": "auto",
            "content": "测试",
            "skill_keys": ["user:other"],
        },
    )
    assert response.status_code == 400
    package(shared, "next")
    client.post("/api/skills/catalog/rescan")
    stale = client.post(
        f"/api/conversations/{conversation}/messages/stream",
        json={
            "execution": "auto",
            "content": "测试",
            "skill_keys": ["shared-0:guide"],
            "skill_catalog_version": before["version"],
        },
    )
    assert stale.status_code == 409
    assert client.get(f"/api/conversations/{conversation}").json()["data"]["messages"] == []


@pytest.mark.parametrize("replacement", ["changed", "deleted", "symlink", "fifo"])
def test_changed_or_unsafe_skill_cannot_be_loaded_from_old_snapshot(
    client, roots, replacement, tmp_path
):
    shared, _ = roots
    file = package(shared)
    client.post("/api/skills/catalog/rescan")
    if replacement == "changed":
        file.write_text(file.read_text().replace("LOCAL_PRIVATE_INSTRUCTIONS", "UPDATED"))
    else:
        file.unlink()
        if replacement == "symlink":
            target = tmp_path / "secret.md"
            target.write_text("PRIVATE")
            file.symlink_to(target)
        elif replacement == "fifo":
            os.mkfifo(file)
    response = client.get("/api/skills/catalog/detail", params={"key": "shared-0:guide"})
    assert response.status_code in {404, 409}


def test_shared_and_private_names_are_distinct_and_invalid_files_are_isolated(client, roots):
    shared, private = roots
    user_id = client.get("/api/auth/me").json()["data"]["id"]
    package(shared)
    package(private / str(user_id))
    invalid = shared / "invalid"
    invalid.mkdir()
    (invalid / "SKILL.md").write_text("bad")
    (shared / "escape").symlink_to(private / str(user_id) / "guide", target_is_directory=True)
    response = client.post("/api/skills/catalog/rescan").json()["data"]
    keys = [item["key"] for item in response["items"]]
    assert {"shared-0:guide", "user:guide"} <= set(keys)
    assert not any("invalid" in key or "escape" in key for key in keys)


def test_saved_catalog_survives_new_provider_instance_and_preserves_version(
    db_session: Session, user, roots
):
    shared, _ = roots
    package(shared)
    snapshot = skill_catalog_service.catalog_snapshot(db_session, user.id, rescan=True)
    db_session.commit()
    registry = skill_catalog_service.registry_from_snapshot(user.id, snapshot)
    loaded = registry.load("shared-0:guide")
    assert loaded is not None
    assert loaded.descriptor.source == "local"
    assert loaded.descriptor.version


def test_rescan_during_approval_preserves_loaded_skill_snapshot(client, db_session, roots):
    shared, _ = roots
    file = package(shared)
    client.post("/api/skills/catalog/rescan")
    conversation = client.post("/api/conversations", json={}).json()["data"]["id"]
    fake = FakeLLM(
        tool_script=[
            tool_reply("rename_conversation", {"conversation_id": conversation, "title": "已整理"}),
            final_reply("完成"),
        ]
    )
    app.dependency_overrides[get_user_llm] = lambda: fake
    try:
        initial = send(client, conversation, skill_keys=["shared-0:guide"], skill_mode="manual")
        pending = initial[-1]
        assert pending["type"] == "approval_required"
        file.write_text(file.read_text().replace("LOCAL_PRIVATE_INSTRUCTIONS", "NEW_INSTRUCTIONS"))
        client.post("/api/skills/catalog/rescan")
        resumed = events(
            client.post(
                f"/api/agent/runs/{pending['run_id']}/approvals/{pending['approval_id']}",
                json={"decision": "approve"},
            )
        )
        assert resumed[-1]["type"] == "run_finished"
        assert "LOCAL_PRIVATE_INSTRUCTIONS" in json.dumps(fake.tool_calls_seen[-1])
        assert "NEW_INSTRUCTIONS" not in json.dumps(fake.tool_calls_seen[-1])
        run = db_session.get(AgentRun, pending["run_id"])
        assert run.skill_snapshot["loaded"][0]["instructions"] == "LOCAL_PRIVATE_INSTRUCTIONS"
    finally:
        app.dependency_overrides.pop(get_user_llm, None)


def test_long_external_metadata_is_supported_and_bad_types_are_isolated(client, roots):
    shared, _ = roots
    package(
        shared,
        "external",
        body="正文" * 2500,
        name="external-workflow-name-with-detailed-label",
        description="长描述" * 100,
    )
    package(shared, "invalid", name=["bad"])
    response = client.post("/api/skills/catalog/rescan").json()["data"]
    keys = [item["key"] for item in response["items"]]
    assert "shared-0:external" in keys
    assert "shared-0:invalid" not in keys


def test_changed_directory_config_stops_approval_resume_with_readable_error(
    client, roots, monkeypatch, tmp_path
):
    shared, _ = roots
    package(shared)
    client.post("/api/skills/catalog/rescan")
    conversation = client.post("/api/conversations", json={}).json()["data"]["id"]
    fake = FakeLLM(
        tool_script=[
            tool_reply("rename_conversation", {"conversation_id": conversation, "title": "修改"}),
        ]
    )
    app.dependency_overrides[get_user_llm] = lambda: fake
    try:
        initial = send(client, conversation, skill_keys=["shared-0:guide"])
        approval = initial[-1]
        assert approval["type"] == "approval_required"
        monkeypatch.setattr(settings, "skill_shared_dirs", [tmp_path.resolve() / "different"])
        output = events(
            client.post(
                f"/api/agent/runs/{approval['run_id']}/approvals/{approval['approval_id']}",
                json={"decision": "approve"},
            )
        )
        assert output == [
            {
                "type": "error",
                "code": 409,
                "message": "Skill 目录配置已变化，请在设置中重新扫描",
            }
        ]
        detail = client.get(
            f"/api/conversations/{conversation}", params={"message_limit": 50}
        ).json()["data"]
        assert detail["runs"][0]["status"] == "failed"
        assert detail["title"] != "修改"
    finally:
        app.dependency_overrides.pop(get_user_llm, None)
