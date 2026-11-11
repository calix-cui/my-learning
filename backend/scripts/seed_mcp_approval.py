"""造一条「停在审批上」的 run，给 E2E 用。

为什么需要它：审批卡片的联调如果依赖真实模型，就得赌模型这次肯不肯调工具；
E2E 必须是确定性的。这里直接把状态写成「已经挂起、等人点」，前端点批准后
走的是真实链路（`decide_approval` → `resume_run` → 真的 MCP 调用），
只是省掉了「模型决定用工具」这一不确定的半步。

用法（只在开发库跑）：

    uv run python scripts/seed_mcp_approval.py --email you@example.com \
        --server-slug echo --tool echo --text "你好，MCP"

输出一行 JSON：`{"conversation_id": 12, "run_id": 34, "approval_id": 56}`。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal
from app.mcp.source import tool_name
from app.models import (
    AgentApproval,
    AgentRun,
    AgentStep,
    Conversation,
    McpServer,
    Message,
    User,
)
from app.models.agent_approval import APPROVAL_PENDING
from app.models.agent_run import RUN_WAITING_APPROVAL
from app.models.agent_step import (
    STEP_TOOL_CALL,
    STEP_USER_MESSAGE,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="造一条等待审批的 Agent run")
    parser.add_argument("--email", required=True, help="账号邮箱")
    parser.add_argument("--server-slug", default="echo", help="已接入的 MCP 服务器 slug")
    parser.add_argument("--tool", default="echo", help="服务器上的工具名")
    parser.add_argument("--text", default="你好，MCP", help="传给工具的 text 参数")
    parser.add_argument("--prompt", default="用回显工具跟世界打个招呼", help="用户那句话")
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is None:
            print(f"没有这个账号：{args.email}", file=sys.stderr)
            return 1
        server = db.scalar(
            select(McpServer).where(
                McpServer.user_id == user.id, McpServer.slug == args.server_slug
            )
        )
        if server is None:
            print(f"没有接入 slug 为 {args.server_slug} 的服务器", file=sys.stderr)
            return 1

        conversation = Conversation(user_id=user.id, title="等待审批的 MCP 调用")
        db.add(conversation)
        db.flush()

        run = AgentRun(
            conversation_id=conversation.id,
            user_id=user.id,
            status=RUN_WAITING_APPROVAL,
            step_count=2,
            model="deepseek-chat",
            started_time=datetime.now(),  # noqa: DTZ005 与 ORM 里的本地时间口径一致
        )
        db.add(run)
        db.flush()

        # 对话里也要有一条用户消息：时间线与审批卡都挂在消息列上渲染
        db.add(Message(conversation_id=conversation.id, role="user", content=args.prompt))
        db.add(
            AgentStep(
                run_id=run.id,
                seq=1,
                kind=STEP_USER_MESSAGE,
                content=args.prompt,
            )
        )
        name = tool_name(args.server_slug, args.tool)
        db.add(
            AgentStep(
                run_id=run.id,
                seq=2,
                kind=STEP_TOOL_CALL,
                tool_name=name,
                tool_args={"text": args.text},
            )
        )
        approval = AgentApproval(
            run_id=run.id,
            user_id=user.id,
            seq=2,
            tool_name=name,
            tool_args={"text": args.text},
            status=APPROVAL_PENDING,
        )
        db.add(approval)
        db.commit()

        print(
            json.dumps(
                {
                    "conversation_id": conversation.id,
                    "run_id": run.id,
                    "approval_id": approval.id,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
