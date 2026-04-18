"""Legislation finder agent for NV Local.

Searches for recent local legislation for a given city using web search,
and creates Google Calendar events for legislative dates via a remote MCP server.
"""

import logging
import os
from datetime import datetime, timedelta

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agents.base_agent_template import BaseReActAgent
from config.constants import AGENT_RECURSION_LIMIT
from config.system_prompts import legislation_finder_sys_prompt
from utils.tools import web_search
from utils.schemas import LegislationFinderState

logger = logging.getLogger(__name__)

_GCAL_MCP_URL = "https://gcal.mintmcp.com/mcp"
_TARGET_GCAL_TOOLS = {"create_event", "get_calendar_events", "update_event"}


def _build_agent(gcal_tools: list) -> object:
    """Build the legislation finder agent graph with the given tools."""
    selected = [t for t in gcal_tools if t.name in _TARGET_GCAL_TOOLS]
    agent = BaseReActAgent(
        state_schema=LegislationFinderState,
        tools=[web_search] + selected,
        system_prompt=lambda state: legislation_finder_sys_prompt.format(
            input_city=state.get("city", "Unknown"),
            last_week_date=(datetime.today() - timedelta(days=7)).strftime("%B %d, %Y"),
            today=datetime.today().strftime("%B %d, %Y"),
        ),
    )
    return agent.build()


async def invoke_legislation_finder(city: str) -> dict:
    """Build and invoke the legislation finder, keeping MCP session alive.

    The MCP streamable-HTTP client uses anyio task groups internally, so
    the session must remain open (via ``async with``) for the entire
    duration of agent execution.  If the MCP connection fails, the agent
    falls back to running with web_search only.
    """
    from langchain_core.messages import HumanMessage

    invoke_kwargs = {
        "input": {
            "city": city,
            "messages": [
                HumanMessage(content=f"Find recent legislation for {city}.")
            ],
        },
        "config": {"recursion_limit": AGENT_RECURSION_LIMIT},
    }

    headers = {}
    api_key = os.getenv("GLAMA_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        async with streamablehttp_client(_GCAL_MCP_URL, headers=headers) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                gcal_tools = await load_mcp_tools(session)
                graph = _build_agent(gcal_tools)
                return await graph.ainvoke(**invoke_kwargs)
    except Exception as exc:
        logger.warning("MCP connection failed (%s), running without calendar tools", exc)
        graph = _build_agent([])
        return await graph.ainvoke(**invoke_kwargs)
