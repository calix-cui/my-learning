"""把网页检索结果中的来源保留在助手消息，供刷新后回放。"""

import json
from typing import Literal, TypedDict
from urllib.parse import urlsplit

MAX_WEB_SOURCES = 5
SEARCH_TOOL_NAMES = {"tavily_search", "web_search", "web_search_exa", "web_search_advanced_exa"}


class EvidenceRef(TypedDict):
    kind: Literal["web"]
    source_id: str
    url: str


def collect_web_evidence(sources: list[EvidenceRef], tool_name: str, result: str) -> None:
    if not tool_name.startswith("mcp__") or tool_name.rsplit("__", 1)[-1] not in SEARCH_TOOL_NAMES:
        return

    # 兼容标准结果对象和 Exa、Tavily MCP 的文本结果。
    try:
        data = json.loads(result)
    except ValueError:
        lines = result.splitlines()
        rows = [{"url": line[5:]} for line in lines if line.startswith("URL: ")]
    else:
        rows = data.get("results", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return

    seen = {item["url"] for item in sources}
    for row in rows:
        if len(sources) >= MAX_WEB_SOURCES:
            break
        url = row.get("url") if isinstance(row, dict) else None
        if not isinstance(url, str) or not _displayable_url(url) or url in seen:
            continue
        sources.append(EvidenceRef(kind="web", source_id=url, url=url))
        seen.add(url)


def _displayable_url(url: str) -> bool:
    if not url or len(url) > 512 or any(ch.isspace() or ch in "<>\\" for ch in url):
        return False
    try:
        parsed = urlsplit(url)
        return bool(
            parsed.scheme in {"https", "http"}
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def append_web_sources(answer: str, sources: list[EvidenceRef]) -> str:
    if not sources:
        return answer
    links = "\n".join(f"- <{source['url']}>" for source in sources)
    return f"{answer}\n\n网页来源\n\n{links}"
