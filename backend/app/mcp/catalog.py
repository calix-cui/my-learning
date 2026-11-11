"""内置「工具市场」清单。

刻意是**代码里的常量**，不从远端拉：
- 供应链风险：市场目录被篡改等于给用户推荐恶意包；
- 清单很小（本期 7 个），随代码发布、随版本更新即可；
- 每个条目带 `updated`，包名变了能一眼看出来该改哪条。

`args` 里的 `{path}` 是占位符：用户在页面上选一个目录后替换。
真正启动前还会过 `app/mcp/specs.py` 的白名单校验（命令限定、https、内网拦截）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.mcp.specs import McpServerSpec, Transport

CATALOG_UPDATED = "2026-11"


@dataclass(frozen=True)
class CatalogEntry:
    """市场里的一张卡片。"""

    slug: str
    display_name: str
    summary: str
    transport: Transport
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    icon: str = "sparkle"
    tags: tuple[str, ...] = ()
    requires_path: bool = False
    docs_url: str | None = None
    updated: str = CATALOG_UPDATED
    extra: dict[str, str] = field(default_factory=dict)

    def build_spec(
        self, *, path: str | None = None, env: dict[str, str] | None = None
    ) -> McpServerSpec:
        """把卡片变成可连接的 `McpServerSpec`。"""
        args = tuple(arg.replace("{path}", path or "") for arg in self.args)
        if self.requires_path and not path:
            # 交给 spec 的校验兜底会得到「命令不合法」这种误导性提示，这里先给准确原因。
            raise ValueError(f"{self.display_name} 需要一个目录或文件路径")
        return McpServerSpec(
            slug=self.slug,
            display_name=self.display_name,
            transport=self.transport,
            command=self.command,
            args=args,
            url=self.url,
            env=dict(env or {}),
        )


CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        slug="filesystem",
        display_name="文件系统",
        summary="读写你指定的目录：列文件、读内容、搜索、按需写入。",
        transport="stdio",
        command="npx",
        args=("-y", "@modelcontextprotocol/server-filesystem", "{path}"),
        icon="folder",
        tags=("本地", "文件"),
        requires_path=True,
        docs_url="https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
    ),
    CatalogEntry(
        slug="git",
        display_name="Git 仓库",
        summary="查提交历史、看 diff、读文件版本，不做写操作。",
        transport="stdio",
        command="uvx",
        args=("mcp-server-git", "--repository", "{path}"),
        icon="git",
        tags=("本地", "开发"),
        requires_path=True,
        docs_url="https://github.com/modelcontextprotocol/servers/tree/main/src/git",
    ),
    CatalogEntry(
        slug="sqlite",
        display_name="SQLite 数据库",
        summary="对单个 SQLite 文件跑只读查询，适合看本地数据。",
        transport="stdio",
        command="uvx",
        args=("mcp-server-sqlite", "--db-path", "{path}"),
        icon="database",
        tags=("本地", "数据"),
        requires_path=True,
        docs_url="https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite",
    ),
    CatalogEntry(
        slug="fetch",
        display_name="网页抓取",
        summary="抓一个 URL 并转成 Markdown，用于读文档与文章。",
        transport="stdio",
        command="uvx",
        args=("mcp-server-fetch",),
        icon="globe",
        tags=("本地", "网络"),
        docs_url="https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
    ),
    CatalogEntry(
        slug="time",
        display_name="时间与时区",
        summary="把时间戳换算成指定时区，或回答「现在几点」。",
        transport="stdio",
        command="uvx",
        args=("mcp-server-time",),
        icon="clock",
        tags=("本地", "工具"),
        docs_url="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
    ),
    CatalogEntry(
        slug="memory",
        display_name="记忆图谱",
        summary="把事实存成知识图谱，跨会话记住你告诉过它的事。",
        transport="stdio",
        command="npx",
        args=("-y", "@modelcontextprotocol/server-memory"),
        icon="brain",
        tags=("本地", "记忆"),
        docs_url="https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
    ),
    CatalogEntry(
        slug="deepwiki",
        display_name="DeepWiki",
        summary="远程服务：问任意公开 GitHub 仓库的架构与用法。",
        transport="http",
        url="https://mcp.deepwiki.com/mcp",
        icon="globe",
        tags=("远程", "文档"),
        docs_url="https://docs.devin.ai/work-with-devin/deepwiki-mcp",
    ),
)

_BY_SLUG = {entry.slug: entry for entry in CATALOG}


def find_entry(slug: str) -> CatalogEntry | None:
    return _BY_SLUG.get(slug)


def catalog_slugs() -> tuple[str, ...]:
    return tuple(_BY_SLUG)


__all__ = ["CATALOG", "CATALOG_UPDATED", "CatalogEntry", "catalog_slugs", "find_entry"]
