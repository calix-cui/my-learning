"""记录模型适配层的每次交互，关联请求、回复、异常与取消。"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from time import perf_counter
from uuid import uuid4

from app.common.dev_trace import trace, trace_context, trace_enabled
from app.config import settings

MAX_STREAM_PREVIEW_CHARS = 32_000


@contextmanager
def llm_exchange(
    model: str,
    mode: str,
    messages: Sequence[Mapping[str, object]],
    tools: Sequence[Mapping[str, object]] = (),
) -> Iterator[Callable[[Mapping[str, object]], None]]:
    if not trace_enabled():
        yield lambda _: None
        return

    exchange_id = uuid4().hex
    started = perf_counter()
    common = {"exchange_id": exchange_id, "model": model, "mode": mode}
    include_payloads = settings.llm_log_payloads
    trace_context(
        "llm.exchange.request", messages, **common, tools=[tool.get("name") for tool in tools]
    )
    if include_payloads:
        trace("llm.exchange.request.body", **common, messages=messages, tools=tools)

    def record_result(reply: Mapping[str, object]) -> None:
        calls = reply.get("tool_calls")
        trace(
            "llm.exchange.response",
            **common,
            duration_ms=round((perf_counter() - started) * 1000),
            model_returned=reply.get("model"),
            finish_reason=reply.get("finish_reason"),
            chars=reply.get("chars", len(str(reply.get("content") or ""))),
            chunks=reply.get("chunks"),
            call_count=len(calls) if isinstance(calls, list) else 0,
        )
        if include_payloads:
            trace("llm.exchange.response.body", **common, reply=reply)

    try:
        yield record_result
    except GeneratorExit:
        trace("llm.exchange.cancel", **common, duration_ms=round((perf_counter() - started) * 1000))
        raise
    except Exception as exc:
        trace(
            "llm.exchange.error",
            **common,
            error_type=type(exc).__name__,
            code=getattr(exc, "code", None),
            duration_ms=round((perf_counter() - started) * 1000),
        )
        raise


def trace_llm_stream(
    model: str, messages: Sequence[Mapping[str, object]], chunks: Iterator[str]
) -> Iterator[str]:
    if not trace_enabled():
        yield from chunks
        return

    with llm_exchange(model, "stream", messages) as record:
        detail = settings.llm_log_payloads
        pieces: list[str] = []
        chars = count = 0
        try:
            for chunk in chunks:
                if detail and chars < MAX_STREAM_PREVIEW_CHARS:
                    pieces.append(chunk[: MAX_STREAM_PREVIEW_CHARS - chars])
                chars += len(chunk)
                count += 1
                yield chunk
        finally:
            # 客户端中止消费时，也关闭上游生成器所持有的 HTTP 流。
            close = getattr(chunks, "close", None)
            if close is not None:
                close()
        record(
            {
                "chars": chars,
                "chunks": count,
                "content": "".join(pieces),
                "truncated": detail and chars > MAX_STREAM_PREVIEW_CHARS,
            }
        )
