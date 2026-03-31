"""Tavily MCP client with profile-based customization.

Search uses an MCP server (tavily_server.py) connected via stdio subprocess.
Content extraction uses the tavily-python SDK directly.
Profiles in config/search_profiles control query shaping and domain filters.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from tavily import AsyncTavilyClient

from utils.mcp._shared import parse_mcp_result

_SERVER_PATH = str(Path(__file__).parent / "tavily_server.py")


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    """Get Tavily API key from environment."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY not set in environment. "
            "Get your key at https://app.tavily.com/"
        )
    return api_key


# ---------------------------------------------------------------------------
# MCP session (stdio subprocess)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_tavily_session():
    """Get MCP session connected to the local Tavily server via stdio.

    Launches tavily_server.py as a subprocess and communicates via stdin/stdout.
    Session is properly cleaned up on exit.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[_SERVER_PATH],
        env={**os.environ, "TAVILY_API_KEY": get_api_key()},
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


# ---------------------------------------------------------------------------
# Profile-based query building
# ---------------------------------------------------------------------------

def load_search_profile(profile_name: str) -> dict[str, Any]:
    """Load search profile config from YAML file."""
    config_path = (
        Path(__file__).parent.parent.parent
        / "config"
        / "search_profiles"
        / f"{profile_name}.yaml"
    )
    if not config_path.exists():
        raise FileNotFoundError(f"Search profile not found: {config_path}")

    with open(config_path) as f:
        profile = yaml.safe_load(f)

    return profile if isinstance(profile, dict) else {}


def _render_terms(terms: list[str], city: str | None) -> list[str]:
    rendered = []
    for term in terms:
        if not isinstance(term, str):
            continue
        rendered.append(term.format(city=city or ""))
    return rendered


def _build_query(query: str, city: str | None, profile: dict[str, Any]) -> str:
    base_query = query.strip()
    prefix = str(profile.get("query_prefix", "")).strip()
    suffix = str(profile.get("query_suffix", "")).strip()
    required_terms = _render_terms(profile.get("required_terms", []), city)
    excluded_terms = _render_terms(profile.get("excluded_terms", []), city)

    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(base_query)
    if city and profile.get("append_city", True):
        parts.append(f'"{city}"')
    if suffix:
        parts.append(suffix)
    parts.extend(required_terms)
    parts.extend(f"-{term}" for term in excluded_terms if term)

    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Search (via MCP)
# ---------------------------------------------------------------------------

async def search_with_profile(
    query: str,
    profile_name: str,
    max_results: int = 10,
    city: str | None = None,
) -> dict[str, Any]:
    """Search Tavily via MCP using a named profile."""
    profile = load_search_profile(profile_name)

    arguments: dict[str, Any] = {
        "query": _build_query(query=query, city=city, profile=profile),
        "max_results": min(max_results, int(profile.get("max_results_cap", 20))),
        "search_depth": profile.get("search_depth", "basic"),
        "topic": profile.get("topic", "general"),
    }

    include_domains = profile.get("include_domains", [])
    exclude_domains = profile.get("exclude_domains", [])
    if isinstance(include_domains, list) and include_domains:
        arguments["include_domains"] = include_domains
    if isinstance(exclude_domains, list) and exclude_domains:
        arguments["exclude_domains"] = exclude_domains

    days = profile.get("days")
    if isinstance(days, int) and days > 0:
        arguments["days"] = days

    async with get_tavily_session() as session:
        result = await session.call_tool("tavily_search", arguments)
        return parse_mcp_result(result)


async def search_legislation(
    query: str,
    city: str,
    max_results: int = 5,
    country: str = "US",
) -> dict[str, Any]:
    """Search for legislation using the legislation profile."""
    del country
    return await search_with_profile(
        query=query,
        profile_name="legislation",
        max_results=max_results,
        city=city,
    )


async def search_political_content(
    query: str,
    city: str | None = None,
    max_results: int = 5,
    country: str = "US",
) -> dict[str, Any]:
    """Search political content using the political profile."""
    del country
    return await search_with_profile(
        query=query,
        profile_name="political",
        max_results=max_results,
        city=city,
    )


# ---------------------------------------------------------------------------
# Result extraction helpers
# ---------------------------------------------------------------------------

def extract_search_results(raw_results: dict[str, Any]) -> list[dict[str, str]]:
    """Extract title/url/description from Tavily results."""
    results = []

    if isinstance(raw_results, dict):
        tavily_results = raw_results.get("results", [])
        if isinstance(tavily_results, list):
            for result in tavily_results:
                if not isinstance(result, dict):
                    continue
                results.append(
                    {
                        "title": str(result.get("title") or "Untitled"),
                        "url": str(result.get("url") or ""),
                        "description": str(result.get("content") or ""),
                    }
                )

    return results


# ---------------------------------------------------------------------------
# Extract (via tavily-python SDK — no MCP equivalent yet)
# ---------------------------------------------------------------------------

async def extract_url_content(urls: list[str]) -> dict[str, str]:
    """Batch-extract page content for URLs using Tavily SDK.

    Returns: dict mapping URL to extracted content (markdown format).
    """
    if not urls:
        return {}

    client = AsyncTavilyClient(api_key=get_api_key())
    response = await client.extract(urls=urls, format="markdown")

    return {
        item["url"]: item["raw_content"]
        for item in response.get("results", [])
        if item.get("raw_content")
    }
