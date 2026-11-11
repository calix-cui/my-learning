"""技能的加载、存储、挂载与执行器注入。

四块：
1. `parse_skill` 的格式校验（写坏 SKILL.md 要在启动时炸，不要带病进上下文）；
2. 内置 + 自定义的合并与 CRUD；
3. 挂载到会话后的 system 消息注入与工具白名单收窄；
4. 接口契约。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent.executor import prepare_run, registry_for, stream_run
from app.auth.service import register_user
from app.common.exceptions import BusinessError
from app.llm.fake import FakeLLM, final_reply
from app.models import Conversation
from app.services import skill_service
from app.skills import BUILTIN_SKILLS, build_system_prompt, builtin_skill, load_builtin_skills
from app.skills.loader import SkillFormatError, parse_skill

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


def test_system_prompt_lists_tools_and_rules():
    skill = builtin_skill("meeting-notes")
    assert skill is not None
    prompt = build_system_prompt(skill, tool_names=["now", "calculator"])
    assert "当前技能：会议纪要" in prompt
    assert "本次对话只开放这些工具：now、calculator" in prompt
    assert "请用户确认" in prompt


# ---------- 2. 合并与 CRUD ----------


def test_list_skills_merges_builtin_and_custom(db_session: Session, user):
    skill_service.create_skill(
        db_session,
        user.id,
        slug="my-own",
        name="自建",
        description="自建技能",
        instructions="正文",
        tools=["calculator"],
    )
    skills = skill_service.list_skills(db_session, user.id)
    slugs = [item.slug for item in skills]
    assert slugs[: len(BUILTIN_SKILLS)] == list(BUILTIN_SKILLS)
    assert "my-own" in slugs
    assert next(item for item in skills if item.slug == "my-own").source == "custom"


def test_create_skill_rejects_builtin_slug_and_duplicate(db_session: Session, user):
    with pytest.raises(BusinessError):
        skill_service.create_skill(
            db_session,
            user.id,
            slug="code-review",
            name="撞内置",
            description="x",
            instructions="正文",
            tools=[],
        )
    skill_service.create_skill(
        db_session, user.id, slug="dup", name="一", description="x", instructions="正文", tools=[]
    )
    with pytest.raises(BusinessError):
        skill_service.create_skill(
            db_session,
            user.id,
            slug="dup",
            name="二",
            description="x",
            instructions="正文",
            tools=[],
        )


def test_update_and_delete_custom_skill(db_session: Session, user):
    created = skill_service.create_skill(
        db_session,
        user.id,
        slug="edit-me",
        name="旧名",
        description="x",
        instructions="正文",
        tools=[],
    )
    updated = skill_service.update_skill(
        db_session, user.id, created.skill_id, name="新名", tools=["now"]
    )
    assert updated.name == "新名"
    assert updated.tools == ("now",)

    skill_service.delete_skill(db_session, user.id, created.skill_id)
    assert skill_service.get_skill(db_session, user.id, "edit-me") is None


def test_other_users_skill_is_invisible(db_session: Session, user):
    other = register_user(db_session, "other-skill@example.com", "password123")
    created = skill_service.create_skill(
        db_session,
        other.id,
        slug="theirs",
        name="他",
        description="x",
        instructions="正文",
        tools=[],
    )
    assert skill_service.get_skill(db_session, user.id, "theirs") is None
    with pytest.raises(BusinessError):
        skill_service.update_skill(db_session, user.id, created.skill_id, name="改不了")


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


def test_mounted_skill_injects_system_message_and_narrows_tools(db_session: Session, user):
    conversation = _conversation(db_session, user)
    skill_service.mount_skill(db_session, user.id, conversation.id, "meeting-notes")

    _, run, context, _ = prepare_run(
        db_session, user_id=user.id, conversation_id=conversation.id, content="记一下会"
    )
    registry = registry_for(db_session, user.id, conversation.id)
    # 白名单只有 now
    assert registry.enabled_names() == ["now"]

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
    assert "本次对话只开放这些工具：now" in first["content"]


def test_deleting_skill_falls_back_to_no_skill(db_session: Session, user):
    created = skill_service.create_skill(
        db_session,
        user.id,
        slug="temp",
        name="临时",
        description="x",
        instructions="正文",
        tools=[],
    )
    conversation = _conversation(db_session, user)
    skill_service.mount_skill(db_session, user.id, conversation.id, "temp")

    skill_service.delete_skill(db_session, user.id, created.skill_id)
    db_session.refresh(conversation)
    assert conversation.skill_slug is None
    assert skill_service.mounted_skill(db_session, user.id, conversation) is None


def test_registry_only_keeps_whitelisted_tools(db_session: Session, user):
    registry = registry_for(db_session, user.id)
    narrowed = registry.only(["calculator", "no-such-tool"])
    assert narrowed.enabled_names() == ["calculator"]
    result = narrowed.execute("now", "{}", user_id=user.id)
    assert result["ok"] is False


# ---------- 4. 接口 ----------


def test_api_lists_builtin_skills(client: TestClient):
    response = client.get("/api/skills")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    slugs = [item["slug"] for item in data["items"]]
    assert "code-review" in slugs
    assert data["mounted"] is None


def test_api_create_update_delete_and_mount(client: TestClient):
    created = client.post(
        "/api/skills",
        json={
            "slug": "api-skill",
            "name": "接口技能",
            "description": "建完再改",
            "instructions": "正文",
            "tools": ["calculator"],
        },
    )
    assert created.status_code == 200, created.text
    skill_id = created.json()["data"]["skill_id"]

    detail = client.get("/api/skills/api-skill")
    assert detail.status_code == 200
    assert detail.json()["data"]["instructions"] == "正文"

    patched = client.patch(f"/api/skills/{skill_id}", json={"name": "改过的名字"})
    assert patched.status_code == 200
    assert patched.json()["data"]["name"] == "改过的名字"

    conversation = client.post("/api/conversations", json={"title": "挂技能"}).json()["data"]["id"]
    mounted = client.put(f"/api/conversations/{conversation}/skill", json={"slug": "api-skill"})
    assert mounted.status_code == 200, mounted.text
    assert mounted.json()["data"]["skill_slug"] == "api-skill"

    listed = client.get(f"/api/skills?conversation_id={conversation}").json()["data"]
    assert listed["mounted"] == "api-skill"
    assert next(i for i in listed["items"] if i["slug"] == "api-skill")["mounted"] is True

    unmounted = client.put(f"/api/conversations/{conversation}/skill", json={"slug": None})
    assert unmounted.json()["data"]["skill_slug"] is None

    deleted = client.delete(f"/api/skills/{skill_id}")
    assert deleted.status_code == 200
    assert client.get("/api/skills/api-skill").status_code == 404


def test_api_rejects_builtin_slug_and_bad_payload(client: TestClient):
    conflict = client.post(
        "/api/skills",
        json={"slug": "code-review", "name": "x", "description": "y", "instructions": "正文"},
    )
    assert conflict.status_code == 400

    bad = client.post(
        "/api/skills",
        json={"slug": "Bad Slug", "name": "x", "description": "y", "instructions": "正文"},
    )
    assert bad.status_code == 400


def test_api_mount_unknown_skill_returns_404(client: TestClient):
    conversation = client.post("/api/conversations", json={"title": "x"}).json()["data"]["id"]
    response = client.put(f"/api/conversations/{conversation}/skill", json={"slug": "ghost-skill"})
    assert response.status_code == 404


def test_api_requires_login(anon_client: TestClient):
    assert anon_client.get("/api/skills").status_code == 401
