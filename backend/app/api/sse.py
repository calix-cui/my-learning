"""SSE 编码：把事件字典变成 `data: {json}\\n\\n` 帧。

对话流式与 agent 流式共用这一处实现，避免两个接口各写一份缓冲/转义规则。
"""

import json
from collections.abc import Iterator

# 关掉 nginx 的响应缓冲，否则增量文本会被攒到最后一次性吐出
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def encode_sse(events: Iterator[dict | None]) -> Iterator[str]:
    """`None` 表示心跳位，写成 SSE 注释：客户端解析器会忽略它。

    心跳不是装饰：拔网线、休眠这类「静默消失」不会触发 `http.disconnect`，
    只有往这条连接写点东西才会失败，执行线程这才知道没人在看。
    """
    try:
        for event in events:
            if event is None:
                yield ": ping\n\n"
                continue
            # 保留中文，便于调试事件流。
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    finally:
        close = getattr(events, "close", None)
        if close is not None:
            close()
