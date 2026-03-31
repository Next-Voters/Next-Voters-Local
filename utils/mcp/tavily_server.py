"""Tavily MCP server wrapping the tavily-python SDK.

Run as a subprocess via stdio transport. Exposes search and extract tools.
Usage: python -m utils.mcp.tavily_server (or run directly)
"""

import os

from fastmcp import FastMCP
from tavily import TavilyClient

mcp = FastMCP("Tavily")


def _get_client() -> TavilyClient:
    return TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))


@mcp.tool
def tavily_search(
    query: str,
    max_results: int = 10,
    search_depth: str = "basic",
    topic: str = "general",
    days: int | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict:
    """Search the web using Tavily.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.
        search_depth: Search depth — "basic" or "advanced".
        topic: Topic type — "general", "news", or "finance".
        days: Restrict results to the last N days.
        include_domains: Only include results from these domains.
        exclude_domains: Exclude results from these domains.
    """
    client = _get_client()
    kwargs: dict = {
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "topic": topic,
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }
    if days is not None:
        kwargs["days"] = days
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains

    return client.search(**kwargs)


@mcp.tool
def tavily_extract(urls: list[str]) -> dict:
    """Extract full page content from a list of URLs.

    Args:
        urls: URLs to extract content from.

    Returns:
        Dict with "results" (successful) and "failed_results" (failed) lists.
    """
    client = _get_client()
    return client.extract(urls=urls, format="markdown")


if __name__ == "__main__":
    mcp.run(transport="stdio")
