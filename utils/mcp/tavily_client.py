"""Tavily Search client with profile-based customization.

This module provides a simple, cloud-hosted search integration using Tavily.
Profiles in config/search_profiles control query shaping and domain filters.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import yaml

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def get_api_key() -> str:
    """Get Tavily API key from environment."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY not set in environment. "
            "Get your key at https://app.tavily.com/"
        )
    return api_key


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


async def search_with_profile(
    query: str,
    profile_name: str,
    max_results: int = 10,
    city: str | None = None,
) -> dict[str, Any]:
    """Search Tavily using a named profile."""
    profile = load_search_profile(profile_name)
    api_key = get_api_key()

    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": _build_query(query=query, city=city, profile=profile),
        "search_depth": profile.get("search_depth", "basic"),
        "topic": profile.get("topic", "general"),
        "max_results": min(max_results, int(profile.get("max_results_cap", 20))),
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }

    include_domains = profile.get("include_domains", [])
    exclude_domains = profile.get("exclude_domains", [])
    if isinstance(include_domains, list) and include_domains:
        payload["include_domains"] = include_domains
    if isinstance(exclude_domains, list) and exclude_domains:
        payload["exclude_domains"] = exclude_domains

    days = profile.get("days")
    if isinstance(days, int) and days > 0:
        payload["days"] = days

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.post(TAVILY_SEARCH_URL, json=payload)
        response.raise_for_status()
        return response.json()


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


def extract_search_results(raw_results: dict[str, Any]) -> list[dict[str, str]]:
    """Extract title/url/description from Tavily results.

    Keeps backward compatibility with the previous Brave-like output shape.
    """
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

        # Backward compatibility fallback
        if not results:
            web_results = raw_results.get("web", {}).get("results", [])
            for result in web_results:
                if not isinstance(result, dict):
                    continue
                results.append(
                    {
                        "title": str(result.get("title") or "Untitled"),
                        "url": str(result.get("url") or ""),
                        "description": str(result.get("description") or ""),
                    }
                )

    return results
