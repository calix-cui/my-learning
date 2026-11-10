"""SSE 事件：执行器产出，接口层只负责把它编码成 `data: {...}`。

事件形状与 `docs/agent.md` §3.5 一一对应；前端按 `type` 分发。
统一在这里构造，避免执行器里散落字符串键名。
"""

from typing import Any

# 事件就是一个带 type 的 dict；用一个别名让签名读起来清楚
AgentEvent = dict[str, Any]


def run_started(run_id: int, conversation_id: int) -> AgentEvent:
    return {"type": "run_started", "run_id": run_id, "conversation_id": conversation_id}


def step_started(seq: int, kind: str) -> AgentEvent:
    return {"type": "step_started", "seq": seq, "kind": kind}


def assistant_text(seq: int, content: str) -> AgentEvent:
    """模型这一步说的话（ReAct 里的 Thought 通道）。"""
    return {"type": "assistant_text", "seq": seq, "content": content}


def tool_call(seq: int, tool: str, args: dict[str, Any] | None) -> AgentEvent:
    return {"type": "tool_call", "seq": seq, "tool": tool, "args": args}


def tool_result(seq: int, tool: str, ok: bool, content: str, duration_ms: int) -> AgentEvent:
    return {
        "type": "tool_result",
        "seq": seq,
        "tool": tool,
        "ok": ok,
        "content": content,
        "duration_ms": duration_ms,
    }


def run_finished(run_id: int, content: str, steps: int, model: str | None) -> AgentEvent:
    return {
        "type": "run_finished",
        "run_id": run_id,
        "content": content,
        "steps": steps,
        "model": model,
    }


def error(code: int, message: str) -> AgentEvent:
    return {"type": "error", "code": code, "message": message}
