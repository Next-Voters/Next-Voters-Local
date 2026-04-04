import logging
from contextlib import AsyncExitStack

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from config.constants import AGENT_RECURSION_LIMIT
from utils.schemas import ChainData
from utils.async_runner import run_async
from utils.mcp.tavily.client import managed_tavily_session
from utils.source_reliability import filter_sources

logger = logging.getLogger(__name__)


async def _invoke_legislation_finder(city: str) -> dict:
    """Invoke the legislation finder agent with an initial task message."""
    from agents.legislation_finder import legislation_finder_agent
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(managed_tavily_session())
        return await legislation_finder_agent.ainvoke(
            {
                "city": city,
                "messages": [
                    HumanMessage(content=f"Find recent legislation for {city}.")
                ],
            },
            config={"recursion_limit": AGENT_RECURSION_LIMIT},
        )


def run_legislation_finder(inputs: ChainData) -> ChainData:
    city = inputs.get("city", "Unknown")
    agent_result = run_async(lambda: _invoke_legislation_finder(city))

    # Extract URLs from raw sources collected by web_search tool calls.
    raw_sources = agent_result.get("raw_legislation_sources", [])
    all_urls = [s["url"] for s in raw_sources if s.get("url")]
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    # Domain-level reliability filter (no API key, no external service).
    # Accepts government, legislative, news, and other non-blocked domains.
    logger.info("Source reliability check for %d unique URLs:", len(unique_urls))
    accepted = filter_sources(unique_urls)
    legislation_sources = [s["url"] for s in accepted]

    logger.info(
        "Legislation finder for %s: %d accepted / %d unique / %d raw",
        city, len(legislation_sources), len(unique_urls), len(raw_sources),
    )
    return {**inputs, "legislation_sources": legislation_sources}


legislation_finder_chain = RunnableLambda(run_legislation_finder)
