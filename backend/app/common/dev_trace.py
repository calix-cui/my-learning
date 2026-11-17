"""开发环境的控制台链路日志。调用方只传可公开的结构化摘要。"""

import json
import logging
from collections.abc import Mapping, Sequence

from app.config import settings

# 复用 Uvicorn 的控制台输出，避免为整个应用打开 DEBUG。
logger = logging.getLogger("uvicorn.error.my_agent.trace")


def trace_enabled() -> bool:
    return settings.app_env == "development" and logger.isEnabledFor(logging.INFO)


def trace(event: str, **fields: object) -> None:
    if trace_enabled():
        logger.info("[my-agent] %s %s", event, json.dumps(fields, ensure_ascii=False))


def trace_context(event: str, messages: Sequence[Mapping[str, object]], **fields: object) -> None:
    if not trace_enabled():
        return
    # 记录顺序与大小，便于核对 prompt 注入和工具结果回传。
    trace(
        event,
        messages=[
            {
                "role": message.get("role"),
                "chars": len(str(message.get("content") or "")),
                "tool_calls": len(calls)
                if isinstance(calls := message.get("tool_calls"), list)
                else 0,
                "tool_call_id": message.get("tool_call_id"),
            }
            for message in messages
        ],
        **fields,
    )
