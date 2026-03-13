import operator

from typing import TypedDict, Annotated

from langchain_core.messages import BaseMessage

from utils.agents import BaseReActAgent
from utils.prompt_builders import build_scraper_builder_prompt
from tools.scraper_builder import code_generator, python_repl, debugger


# === STATE DEFINITION ===


class ScraperBuilderState(TypedDict):
    """State for the scraper builder agent."""

    messages: Annotated[list[BaseMessage], operator.add]


# === TOOL LIST ===

tools = [code_generator, python_repl, debugger]


# === AGENT CONSTRUCTION ===

system_prompt = build_scraper_builder_prompt()

_agent = BaseReActAgent(
    state_schema=ScraperBuilderState,
    tools=tools,
    system_prompt=system_prompt,
)

scraper_builder_agent = _agent.build()
