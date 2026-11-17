"""测试用网页检索服务器，以 MCP 标准传输返回固定来源。"""

from mcp.server.mcpserver import MCPServer

server = MCPServer(name="web-search-fixture", version="0.1.0")


@server.tool()
def web_search(query: str) -> str:
    """搜索网页并返回来源。"""
    return (
        f"学习主题：{query}\n"
        "Detailed Results:\n\n"
        "Title: Function calling\n"
        "URL: https://developers.openai.com/api/docs/guides/function-calling\n"
        "Content: 工具调用由应用执行。\n"
        "URL: javascript:alert(1)"
    )


if __name__ == "__main__":
    server.run(transport="stdio")
