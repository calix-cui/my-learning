"""清掉本地开发库里由 E2E / 手工调试留下的演示账号。

这些账号的邮箱都是 `<前缀>-<时间戳>@example.com`（`chat-e2e-`、`tools-e2e-`、
`ui-`、`dbg`、`theme-` 等），由 `pnpm acceptance:*` 脚本注册。它们会：
- 让「注册页 / 登录页」的演示账号列表越堆越多；
- 让 `users` 表与级联的会话、消息、run、审批表一起膨胀。

用法（在 `backend/` 目录下）：

    uv run python scripts/cleanup_demo_accounts.py --dry-run   # 只看会删什么
    uv run python scripts/cleanup_demo_accounts.py --yes       # 真删

删除依赖数据库的 `ON DELETE CASCADE`：删 `users` 一行会带走该账号的
`sessions` / `user_settings` / `conversations` → `messages`
→ `agent_runs` → `agent_steps` / `agent_approvals`。

真实账号不会被删：判定条件只有「邮箱域名是 example.com」这一条，
`--keep` 可以额外保留指定邮箱。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.models import (
    AgentApproval,
    AgentRun,
    AgentStep,
    Conversation,
    LoginSession,
    Message,
    User,
    UserSettings,
)

DEMO_DOMAIN = "@example.com"


def count_rows(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def main() -> int:
    parser = argparse.ArgumentParser(description="清掉开发库里的 E2E 演示账号")
    parser.add_argument("--yes", action="store_true", help="真的删除（默认只预览）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不删除（默认行为）")
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        help="额外保留的邮箱，可传多次",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        query = select(User).where(User.email.like(f"%{DEMO_DOMAIN}"))
        if args.keep:
            query = query.where(User.email.notin_(args.keep))
        victims = list(db.scalars(query.order_by(User.id)))
        if not victims:
            print("没有需要清理的演示账号。")
            return 0

        ids = [u.id for u in victims]
        print(f"命中 {len(victims)} 个演示账号（{DEMO_DOMAIN}）：")
        for user in victims[:10]:
            print(f"  - #{user.id} {user.email}")
        if len(victims) > 10:
            print(f"  … 其余 {len(victims) - 10} 个省略")

        # 级联删除之前先报一遍「会连带删掉多少」，避免用户对数据量无感
        convs = db.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.user_id.in_(ids))
        )
        msgs = db.scalar(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.user_id.in_(ids))
        )
        runs = db.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.user_id.in_(ids))
        )
        print(f"连带删除：会话 {convs} · 消息 {msgs} · agent run {runs}")

        if not args.yes:
            print("\n这是预览。确认无误后加 --yes 再跑一次。")
            return 0

        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()

        print("\n删除完成，当前库：")
        for model, label in (
            (User, "users"),
            (LoginSession, "sessions"),
            (UserSettings, "user_settings"),
            (Conversation, "conversations"),
            (Message, "messages"),
            (AgentRun, "agent_runs"),
            (AgentStep, "agent_steps"),
            (AgentApproval, "agent_approvals"),
        ):
            print(f"  {label:<16} {count_rows(db, model)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
