"""MCP client utilities for connecting to external services."""

from utils.mcp.tavily_client import (
    get_api_key,
    get_tavily_session,
    search_legislation,
    search_political_content,
    extract_search_results,
    extract_url_content,
)
from utils.mcp.wikidata_client import (
    get_wikidata_session,
    search_entity,
    get_org_classification,
    analyze_reliability,
)
from utils.mcp.political_figures_client import (
    get_political_figures_session,
    find_political_figures,
    extract_commentary,
    search_politician_tweets,
)

__all__ = [
    # Tavily
    "get_api_key",
    "get_tavily_session",
    "search_legislation",
    "search_political_content",
    "extract_search_results",
    "extract_url_content",
    # Wikidata
    "get_wikidata_session",
    "search_entity",
    "get_org_classification",
    "analyze_reliability",
    # Political Figures
    "get_political_figures_session",
    "find_political_figures",
    "extract_commentary",
    "search_politician_tweets",
]
