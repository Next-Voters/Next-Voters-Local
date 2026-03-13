import operator

from typing import TypedDict, Annotated, NotRequired

from langchain_core.messages import BaseMessage

from utils.models import ReflectionEntry
from utils.agents import BaseReActAgent
from utils.prompt_builders import build_legislation_finder_prompt
from tools.legislation_finder import web_search, reflection_tool, reliability_analysis


# === STATE DEFINITION ===


class LegislationFinderState(TypedDict):
    """State for the legislation finder agent."""

    messages: Annotated[list[BaseMessage], operator.add]
    reflection_list: NotRequired[Annotated[list[ReflectionEntry], operator.add]]
    city: NotRequired[str]

    raw_legislation_sources: NotRequired[Annotated[list[str], operator.add]]
    reliable_legislation_sources: NotRequired[Annotated[list[str], operator.add]]


# === TOOL LIST ===

tools = [web_search, reflection_tool, reliability_analysis]


# === AGENT CONSTRUCTION ===

system_prompt = build_legislation_finder_prompt()

_agent = BaseReActAgent(
    state_schema=LegislationFinderState,
    tools=tools,
    system_prompt=system_prompt,
)

legislation_finder_agent = _agent.build()
