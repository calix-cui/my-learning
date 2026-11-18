"""第五步真实模型联调：断线后能否认领这次提交。

对着本地真实后端（真实 DeepSeek + 真实 MySQL）跑，不模拟任何东西：
1. 注册一个一次性账号，建会话；
2. 发一条会触发工具调用的消息，读到第一帧就掐断连接（模拟断流）；
3. 用同一个 request_id 认领，看服务端是否记录了「运行被中断」；
4. 用一个没提交过的 request_id 查，确认返回 404 的可重发文案；
5. 再正常跑一次完整流式，确认没被这次改动弄坏。
"""

import asyncio
import json
import sys
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000/api"
STAMP = str(int(time.time()))
EMAIL = f"reconnect-{STAMP}@example.com"
PASSWORD = "reconnect-pass-123"

ok = True


def check(name: str, passed: bool, detail: str = "") -> None:
    global ok
    ok = ok and passed
    print(f"[{'ok' if passed else 'FAIL'}] {name}{f'：{detail}' if detail else ''}")


async def main() -> int:
    # trust_env=False：本机 http_proxy/NO_PROXY（含 [::1]）会让 httpx 解析地址失败
    async with httpx.AsyncClient(base_url=BASE, timeout=120.0, trust_env=False) as client:
        r = await client.post(
            "/auth/register",
            json={"email": EMAIL, "password": PASSWORD, "display_name": "联调账号"},
        )
        check("注册一次性账号", r.status_code == 200, str(r.status_code))
        r = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        check("登录拿到会话", r.status_code == 200, str(r.status_code))
        headers: dict[str, str] = {}

        r = await client.post("/conversations", json={"title": "断线联调"}, headers=headers)
        conversation_id = r.json()["data"]["id"]
        check("建会话", r.status_code == 200, f"id={conversation_id}")

        # ---- 1. 断流：读到第一帧就断开 ----
        request_id = str(uuid.uuid4())
        frames: list[str] = []
        try:
            async with client.stream(
                "POST",
                f"/conversations/{conversation_id}/messages/stream",
                json={
                    "content": "用计算器算出 3 的 5 次方，然后一句话告诉我结果",
                    "execution": "auto",
                    "request_id": request_id,
                },
                headers=headers,
            ) as response:
                check("流式请求开流成功", response.status_code == 200, str(response.status_code))
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        frames.append(line[5:].strip())
                        if len(frames) >= 1:
                            break
                # 主动断开：不等终态，正是用户关页面/掉网的样子
        except httpx.HTTPError as exc:  # 断开本身可能抛错，属预期
            print(f"     （断开时的异常，属预期：{type(exc).__name__}）")
        check("断开前收到了至少一帧", len(frames) >= 1, f"{len(frames)} 帧：{frames[:1]}")

        first = json.loads(frames[0]) if frames else {}
        run_id = first.get("run_id")
        print(f"     run_started：run_id={run_id} 事件={first.get('type')}")

        # 等后端把这次运行收尾（断流即失败）；真实模型可能先跑完当前一轮
        for _ in range(120):
            await asyncio.sleep(0.5)
            r = await client.get(
                f"/conversations/{conversation_id}", params={"message_limit": 50}, headers=headers
            )
            runs = r.json()["data"]["runs"]
            if runs and runs[0]["status"] in {"failed", "completed", "cancelled"}:
                break
        runs = r.json()["data"]["runs"]
        check("历史页能看到这次运行", len(runs) >= 1, f"{len(runs)} 条")
        summary = runs[0] if runs else {}
        check("摘要带上了 request_id", summary.get("request_id") == request_id, summary.get("request_id"))
        check("断流被记成失败", summary.get("status") == "failed", summary.get("status"))
        check(
            "失败原因来自服务端",
            summary.get("error_message") == "运行被中断",
            str(summary.get("error_message")),
        )
        check("有结束时间", bool(summary.get("finished_time")), str(summary.get("finished_time")))

        # ---- 2. 按 request_id 认领 ----
        r = await client.get(
            f"/conversations/{conversation_id}/agent/runs",
            params={"request_id": request_id},
            headers=headers,
        )
        claimed = r.json()["data"]["items"] if r.status_code == 200 else []
        check(
            "按 request_id 认领到这次提交",
            r.status_code == 200 and len(claimed) == 1 and claimed[0]["id"] == summary.get("id"),
            f"HTTP {r.status_code}",
        )

        # ---- 3. 没提交过的 request_id ----
        r = await client.get(
            f"/conversations/{conversation_id}/agent/runs",
            params={"request_id": str(uuid.uuid4())},
            headers=headers,
        )
        body = r.json()
        check("没落库的 request_id 返回 404", r.status_code == 404, str(r.status_code))
        check(
            "404 文案能指导重发",
            "没有落库，可以重新发送" in str(body.get("message")),
            str(body.get("message")),
        )

        # ---- 4. 单点详情与增量步骤 ----
        run_id = summary.get("id")
        r = await client.get(f"/agent/runs/{run_id}", headers=headers)
        detail = r.json()["data"] if r.status_code == 200 else {}
        check("单点详情能读到运行", r.status_code == 200 and detail.get("id") == run_id, str(r.status_code))
        check(
            "详情带失败原因与会话号",
            detail.get("error_message") == "运行被中断"
            and detail.get("conversation_id") == conversation_id,
            f"{detail.get('error_message')} / {detail.get('conversation_id')}",
        )

        steps = page_steps = detail.get("steps") or []
        del page_steps
        r = await client.get(f"/agent/runs/{run_id}/steps", headers=headers)
        page = r.json()["data"]
        check(
            "步骤接口返回状态而不是裸数组",
            isinstance(page, dict) and "items" in page and "status" in page,
            f"keys={sorted(page)}" if isinstance(page, dict) else "not dict",
        )
        check(
            "可见步骤数与详情一致",
            page.get("visible_step_count") == len(page.get("items") or []),
            f"{page.get('visible_step_count')} vs {len(page.get('items') or [])}",
        )

        if steps:
            mid = steps[len(steps) // 2]["seq"]
            r = await client.get(
                f"/agent/runs/{run_id}/steps", params={"since_seq": mid}, headers=headers
            )
            inc = r.json()["data"]
            check(
                "since_seq 只回后续步骤",
                all(item["seq"] > mid for item in inc["items"])
                and len(inc["items"]) == max(0, len(steps) - mid),
                f"since={mid} 回 {len(inc['items'])} 条 / 共 {len(steps)} 条",
            )
            check(
                "增量读仍带整次运行状态",
                inc.get("status") == "failed"
                and inc.get("visible_step_count") == page.get("visible_step_count"),
                f"{inc.get('status')} / {inc.get('visible_step_count')}",
            )

        # ---- 5. 正常跑完一次，确认没弄坏 ----
        normal_id = str(uuid.uuid4())
        events: list[dict] = []
        async with client.stream(
            "POST",
            f"/conversations/{conversation_id}/messages/stream",
            json={"content": "只回四个字：联调通过", "execution": "auto", "request_id": normal_id},
            headers=headers,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    events.append(json.loads(line[5:]))
        kinds = [event.get("type") for event in events]
        check("完整流式跑通", "run_finished" in kinds, f"事件={kinds}")
        finished = next((e for e in events if e["type"] == "run_finished"), {})
        check("终态给出正文", bool(finished.get("content")), str(finished.get("content"))[:40])

        r = await client.get(
                f"/conversations/{conversation_id}", params={"message_limit": 50}, headers=headers
            )
        runs = r.json()["data"]["runs"]
        latest = runs[0] if runs else {}
        check(
            "这次运行落库为完成且带 request_id",
            latest.get("status") == "completed" and latest.get("request_id") == normal_id,
            f"{latest.get('status')} / {latest.get('request_id')}",
        )

    print("\n结果：", "全部通过" if ok else "有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
