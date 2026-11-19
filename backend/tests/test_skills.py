"""技能的加载、挂载与执行器注入。

三块：
1. `parse_skill` 的格式校验（写坏 SKILL.md 要在启动时炸，不要带病进上下文）；
2. 内置技能的加载、发现与快照隔离；
3. 挂载到会话后的 system 消息注入与工具白名单收窄，以及接口契约。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent.executor import prepare_run, registry_for, stream_run
from app.common.exceptions import BusinessError
from app.llm.fake import FakeLLM, final_reply
from app.models import Conversation
from app.services import skill_service
from app.skills import build_system_prompt, builtin_skill, load_builtin_skills
from app.skills.loader import SkillFormatError, parse_skill
from app.skills.providers.filesystem import FileSystemSkillProvider
from app.skills.registry import SkillRegistry

VALID = """---
slug: demo-skill
name: 演示技能
description: 用来测试的技能
tools:
  - calculator
---

正文第一段。
"""


# ---------- 1. 解析 ----------


def test_parse_skill_reads_frontmatter_and_body():
    skill = parse_skill(VALID)
    assert skill.slug == "demo-skill"
    assert skill.name == "演示技能"
    assert skill.tools == ("calculator",)
    assert skill.instructions == "正文第一段。"
    assert skill.source == "builtin"


@pytest.mark.parametrize(
    "text",
    [
        "没有 frontmatter",
        "---\nslug: demo\nname: x\n",
        "---\nslug: Bad_Slug\nname: x\ndescription: y\n---\n正文",
        "---\nslug: demo\nname: x\n---\n正文",
        "---\nslug: demo\nname: x\ndescription: y\n---\n",
        "---\nslug: demo\nname: x\ndescription: y\ntools: nope\n---\n正文",
    ],
)
def test_parse_skill_rejects_bad_input(text):
    with pytest.raises(SkillFormatError):
        parse_skill(text)


def test_builtin_skills_load_three_packages():
    skills = load_builtin_skills()
    assert {"code-review", "meeting-notes", "decision-brief"} <= set(skills)
    for skill in skills.values():
        assert skill.instructions.strip()
        assert skill.description.strip()


def test_skill_registry_discovers_metadata_then_loads_content(tmp_path):
    root = tmp_path / "skills"
    package = root / "quick-start"
    package.mkdir(parents=True)
    path = package / "SKILL.md"
    path.write_text(
        "---\nname: Quick Start\ndescription: A short guide.\n---\n\nFull instructions.",
        encoding="utf-8",
    )
    registry = SkillRegistry([FileSystemSkillProvider(root)])

    [descriptor] = registry.discover()
    assert descriptor.key == "builtin:quick-start"
    assert descriptor.name == "Quick Start"
    assert not hasattr(descriptor, "instructions")

    loaded = registry.load(descriptor.key)
    assert loaded is not None
    assert loaded.instructions == "Full instructions."
    assert loaded.content_hash


def test_filesystem_skill_discovery_uses_snapshot_and_rescan_isolates_invalid_files(tmp_path):
    root = tmp_path / "skills"
    first = root / "first"
    first.mkdir(parents=True)
    (first / "SKILL.md").write_text(
        "---\nname: First\ndescription: first version\n---\nbody", encoding="utf-8"
    )
    invalid = root / "invalid"
    invalid.mkdir()
    (invalid / "SKILL.md").write_text("not frontmatter", encoding="utf-8")
    provider = FileSystemSkillProvider(root)

    assert [item.slug for item in provider.discover()] == ["first"]
    (root / "second").mkdir()
    (root / "second" / "SKILL.md").write_text(
        "---\nname: Second\ndescription: second skill\n---\nbody", encoding="utf-8"
    )

    assert [item.slug for item in provider.discover()] == ["first"]
    assert [item.slug for item in FileSystemSkillProvider(root).discover()] == ["first", "second"]


def test_system_prompt_lists_tools_and_rules():
    skill = builtin_skill("meeting-notes")
    assert skill is not None
    prompt = build_system_prompt(skill, tool_names=["now", "calculator"])
    assert "当前技能：会议纪要" in prompt
    assert "本次对话只开放这些工具：now、calculator" in prompt
    assert "请用户确认" in prompt


# ---------- 2. 合并与 CRUD ----------


# ---------- 3. 挂载与执行器 ----------


def _conversation(db: Session, user) -> Conversation:
    conversation = Conversation(user_id=user.id, title="技能测试")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def test_mount_and_unmount_skill(db_session: Session, user):
    conversation = _conversation(db_session, user)
    skill_service.mount_skill(db_session, user.id, conversation.id, "meeting-notes")
    db_session.refresh(conversation)
    assert conversation.skill_slug == "meeting-notes"

    skill_service.mount_skill(db_session, user.id, conversation.id, None)
    db_session.refresh(conversation)
    assert conversation.skill_slug is None

    with pytest.raises(BusinessError):
        skill_service.mount_skill(db_session, user.id, conversation.id, "no-such-skill")


def test_mounted_skill_injects_system_message_without_narrowing_tools(db_session: Session, user):
    conversation = _conversation(db_session, user)
    skill_service.mount_skill(db_session, user.id, conversation.id, "meeting-notes")

    _, run, context, _ = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="记一下会"
    )
    registry = registry_for(db_session, user.id, conversation.id)
    assert {"now", "calculator"} <= set(registry.enabled_names())

    captured: list = []

    class Recorder(FakeLLM):
        def chat_with_tools(self, messages, tools, **kwargs):  # type: ignore[override]
            captured.append(messages)
            return super().chat_with_tools(messages, tools, **kwargs)

    llm = Recorder(model="fake", tool_script=[final_reply("好了")])
    list(
        stream_run(
            db_session,
            run=run,
            conversation=conversation,
            messages=context,
            llm=llm,
            is_first_message=True,
            user_id=user.id,
            registry=registry,
        )
    )

    assert captured, "模型应当被调用一次"
    first = captured[0][0]
    assert first["role"] == "system"
    assert "当前技能：会议纪要" in first["content"]
    assert "本次运行可用的工具：" in first["content"]
    assert "calculator" in first["content"]


def test_registry_only_keeps_whitelisted_tools(db_session: Session, user):
    registry = registry_for(db_session, user.id)
    narrowed = registry.only(["calculator", "no-such-tool"])
    assert narrowed.enabled_names() == ["calculator"]
    result = narrowed.execute("now", "{}", user_id=user.id)
    assert result["ok"] is False


# ---------- 4. 接口 ----------


def test_api_mount_unknown_skill_returns_404(client: TestClient):
    conversation = client.post("/api/conversations", json={"title": "x"}).json()["data"]["id"]
    response = client.put(f"/api/conversations/{conversation}/skill", json={"slug": "ghost-skill"})
    assert response.status_code == 404


def test_api_requires_login(anon_client: TestClient):
    assert anon_client.get("/api/skills/catalog").status_code == 401
