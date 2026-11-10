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


def encode_sse(events: Iterator[dict]) -> Iterator[str]:
    for event in events:
        # ensure_ascii=False：中文直接输出，不转成 \uXXXX，方便 curl 观察
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
