"""Tools for the Political Commentry Agent (Agent 2).

Contains: political_figure_finder, search_political_commentary.
All tools return Command objects to update LangGraph state.

Uses the official Brave Search MCP server (via Smithery) with Goggles.
"""

from typing import Annotated

import requests
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt.tool_node import InjectedState
from langgraph.types import Command

from config.system_prompts.political_commentary import comment_extraction_prompt
from utils.tools import (
    detect_country_from_city,
    fetch_canadian_political_figures,
    fetch_american_political_figures,
)
from utils.mcp.brave_client import search_political_content, extract_search_results
from utils.llm import get_mini_llm

mini_model = get_mini_llm()


def fetch_page_content(url: str) -> str:
    """Fetch the raw text content from a URL."""
    try:
        headers = {
            "User-Agent": "PoliticalCommentaryAgent/1.0",
            "Accept": "text/html,application/xhtml+xml",
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text[:15000]
    except Exception as e:
        return f"Failed to fetch content: {e}"


def extract_commentary_with_llm(url: str, politician: str, query: str) -> str:
    """Extract the political commentary from a page using LLM."""
    page_content = fetch_page_content(url)
    system_prompt = comment_extraction_prompt.format(politician=politician, query=query)
    try:
        response = mini_model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Page content:\n\n{page_content}"},
            ]
        )
        return response.content.strip()
    except Exception as e:
        return f"Failed to extract commentary: {e}"


@tool
def political_figure_finder(
    tool_call_id: Annotated[str, InjectedToolCallId],
    city: Annotated[str, InjectedState("city")],
) -> Command:
    """Find political figures (candidates, elected officials) for a specific city.

    Queries an external data service to find Canadian and American political
    candidates and elected officials for the given city. The country is
    automatically detected using geocoding.

    Args:
        tool_call_id: Injected by LangGraph — used to associate the ToolMessage.
        city: The city name to search for political figures (injected from state).

    Returns:
        A Command object that updates the state with political figure data.
    """
    try:
        country_code = detect_country_from_city(city)
    except Exception as e:
        return Command(
            update={
                "political_figures": [],
                "messages": [
                    ToolMessage(
                        content=f"Failed to detect country for city '{city}': {e}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    if country_code not in ("CA", "US"):
        return Command(
            update={
                "political_figures": [],
                "messages": [
                    ToolMessage(
                        content=f"Unsupported country: {country_code}. Only Canada (CA) and USA (US) are supported.",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    country = "canada" if country_code == "CA" else "usa"

    try:
        if country == "canada":
            political_figures = fetch_canadian_political_figures(city)
        else:
            political_figures = fetch_american_political_figures(city)

        summary_lines = [
            f"Found {len(political_figures)} political figure(s) in {city}, {country}:"
        ]
        for pf in political_figures:
            summary_lines.append(
                f"  - {pf['name']} ({pf.get('position', 'Unknown position')})"
            )

        return Command(
            update={
                "political_figures": political_figures,
                "country": country,
                "messages": [
                    ToolMessage(
                        content="\n".join(summary_lines),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except Exception as e:
        error_msg = f"Failed to find political figures: {e}"
        return Command(
            update={
                "political_figures": [],
                "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
            }
        )


@tool
async def search_political_commentary(
    query: str,
    politician: str,
    city: Annotated[str, InjectedState("city")],
    tool_call_id: Annotated[str, InjectedToolCallId],
    max_results: int = 5,
) -> Command:
    """Search for political commentary and extract the politician's statements.

    Uses Brave Web Search MCP with Goggles to find authoritative political
    content, then uses an LLM to extract the politician's actual commentary
    from each source. Returns unified results with politician name, source URL,
    and extracted comment.

    Args:
        query: The search query — e.g. "Austin mayor political commentary" or
               "John Smith city council news opinion".
        politician: The name of the politician to search commentary for.
        city: The city context for local political content (from state).
        tool_call_id: Injected by LangGraph — used to associate the ToolMessage.
        max_results: Maximum number of results to return (default 5).

    Returns:
        A Command object that updates the state with political commentary
        (containing politician, source_url, and comment).
    """
    try:
        raw_results = await search_political_content(
            query=query,
            city=city,
            max_results=max_results,
        )

        results = extract_search_results(raw_results)

        if not results:
            return Command(
                update={
                    "political_commentary": [],
                    "messages": [
                        ToolMessage(
                            content=f"No political commentary found for query '{query}'.",
                            tool_call_id=tool_call_id,
                        )
                    ],
                }
            )

        political_commentary = []
        for r in results:
            url = r.get("url", "")
            extracted_comment = extract_commentary_with_llm(url, politician, query)
            political_commentary.append(
                {
                    "politician": politician,
                    "source_url": url,
                    "comment": extracted_comment,
                }
            )

        summary_lines = [
            f"Found {len(political_commentary)} commentary source(s) for {politician}:"
        ]
        for pc in political_commentary:
            comment_preview = (
                pc["comment"][:100] + "..."
                if len(pc["comment"]) > 100
                else pc["comment"]
            )
            summary_lines.append(f"  - {pc['source_url']}: {comment_preview}")

        return Command(
            update={
                "political_commentary": political_commentary,
                "messages": [
                    ToolMessage(
                        content="\n".join(summary_lines),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except ValueError as e:
        error_msg = f"Brave Search API key not configured: {e}"
        return Command(
            update={
                "political_commentary": [],
                "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
            }
        )
    except Exception as e:
        error_msg = f"Failed to search political commentary: {e}"
        return Command(
            update={
                "political_commentary": [],
                "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
            }
        )
