"""Live local Skill acceptance using synthetic data and an automatically removed account.

Run from backend: .venv/bin/python -m scripts.skill_runtime_acceptance
Uses the running service's configured model (may incur model usage charges).
"""

import json
import secrets
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AgentRun, User

BASE_URL = "http://127.0.0.1:8000"
RESOURCE = "references/checklist.md"


def request(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code != 200:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}")
    payload = response.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"{method} {path}: business error {payload.get('code')}")
    return payload.get("data")


def stream(client: httpx.Client, conversation_id: int, mode: str) -> list[dict]:
    instruction = (
        "请按会议纪要技能整理以下虚构记录。先实际加载该技能，再实际读取它的 "
        "references/checklist.md 参考资料，核对后给出简短纪要。不要调用其他工具。"
        if mode != "off"
        else "请直接整理以下虚构会议记录，不使用技能或工具。"
    )
    prompt = instruction + "记录：小林周五前发送报价；会上决定先试用一周；预算尚未确定。"
    events = []
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/agent/stream",
        json={"content": prompt, "skill_mode": mode},
    ) as response:
        if response.status_code != 200:
            raise RuntimeError(f"stream HTTP {response.status_code}")
        for line in response.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:])
                events.append(event)
                print(
                    json.dumps(
                        {"mode": mode, "event": event["type"], "ok": event.get("ok")},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    if events and events[-1]["type"] == "error":
        raise RuntimeError(f"SSE error {events[-1].get('code')}: {events[-1].get('message')}")
    assert events and events[-1]["type"] == "run_finished", "run did not finish"
    assert events[-1]["content"].strip(), "missing final reply"
    assert events[-1]["model"] != "fake", "live-model acceptance requires a real model"
    return events


def main() -> None:
    database = make_url(settings.database_url)
    if database.host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("This acceptance script only supports a local database")
    email = f"skill-acceptance-{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    engine = create_engine(settings.database_url)
    user_id = None
    try:
        with httpx.Client(base_url=BASE_URL, trust_env=False, timeout=120) as client:
            try:
                user = request(
                    client,
                    "POST",
                    "/api/auth/register",
                    json={"email": email, "password": password},
                )
                user_id = user["id"]
                for path in [
                    "/api/settings/model",
                    "/api/settings/appearance",
                    "/api/conversations",
                ]:
                    request(client, "GET", path)
                print("settings and conversation endpoints: PASS", flush=True)
                for mode in ["auto", "manual", "off"]:
                    conversation = request(
                        client, "POST", "/api/conversations", json={"title": "Skill 验收临时会话"}
                    )
                    cid = conversation["id"]
                    if mode in {"manual", "off"}:
                        request(
                            client,
                            "PUT",
                            f"/api/conversations/{cid}/skill",
                            json={"slug": "meeting-notes"},
                        )
                    events = stream(client, cid, mode)
                    run_id = events[0]["run_id"]
                    history = request(client, "GET", f"/api/conversations/{cid}/agent/runs")[
                        "items"
                    ][0]
                    detail = request(client, "GET", f"/api/conversations/{cid}")
                    assert history["status"] == "completed"
                    assert [item["role"] for item in detail["messages"]] == ["user", "assistant"]
                    assert detail["messages"][-1]["content"] == events[-1]["content"]
                    with Session(engine) as db:
                        run = db.scalar(
                            select(AgentRun).where(
                                AgentRun.id == run_id, AgentRun.user_id == user_id
                            )
                        )
                        assert run is not None and run.skill_mode == mode
                        if mode == "off":
                            assert not run.skill_snapshot["loaded"]
                            assert not any(event["type"].startswith("skill_") for event in events)
                        else:
                            assert any(
                                event["type"] == "skill_loaded"
                                and event["skill_key"] == "builtin:meeting-notes"
                                for event in events
                            )
                            assert any(
                                event["type"] == "skill_resource"
                                and event["ok"]
                                and event["path"] == RESOURCE
                                for event in events
                            )
                            assert any(
                                step["kind"] == "skill_resource" and step["ok"]
                                for step in history["steps"]
                            )
                            loaded = next(
                                item
                                for item in run.skill_snapshot["loaded"]
                                if item["descriptor"]["key"] == "builtin:meeting-notes"
                            )
                            assert "会议纪要交付检查" in loaded["resource_contents"][RESOURCE]
                    print(
                        f"{mode}: live model + SSE + MySQL snapshot + message/history replay PASS",
                        flush=True,
                    )
            finally:
                if user_id is not None:
                    request(client, "DELETE", "/api/auth/me", json={"password": password})
                    with Session(engine) as db:
                        assert db.get(User, user_id) is None
                        assert (
                            db.scalar(select(AgentRun.id).where(AgentRun.user_id == user_id))
                            is None
                        )
                    print("temporary account and runs removed: PASS", flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
