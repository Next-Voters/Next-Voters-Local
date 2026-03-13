import operator
from datetime import datetime, timedelta

from typing import TypedDict, Annotated, NotRequired

from langchain_core.messages import BaseMessage

from utils.models import ReflectionEntry
from utils.agents import BaseReActAgent
from utils.prompts import legislation_finder_sys_prompt
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


# === PROMPT BUILDER ===


def build_legislation_finder_prompt(state: LegislationFinderState) -> str:
    """Build the formatted system prompt from current state.

    This function is invoked on each model call with the current state,
    ensuring the prompt reflects fresh values:
    - City from state
    - Reflection list from state (accumulated across iterations)
    - Current date range

    Args:
        state: Current agent state (contains messages, city, reflection_list)

    Returns:
        Fully formatted system prompt string ready for the LLM.
    """
    city = state.get("city", "Unknown")
    reflection_list = state.get("reflection_list", [])

    # Parse reflection list into readable format for the prompt
    parsed_reflection_list = "\n".join(
        [
            f"{r.reflection}"
            f"\n  Gaps: {', '.join(r.gaps_identified) or 'None'}"
            f"\n  Next action: {r.next_action}"
            for r in reflection_list
        ]
    )

    # Format the base prompt template with current state values
    return legislation_finder_sys_prompt.format(
        input_city=city,
        last_week_date=(datetime.today() - timedelta(days=7)).strftime("%B %d"),
        today=datetime.today().strftime("%B %d"),
        reflections=parsed_reflection_list,
    )


# === AGENT CONSTRUCTION ===

_agent = BaseReActAgent(
    state_schema=LegislationFinderState,
    tools=tools,
    prompt_builder=build_legislation_finder_prompt,
)

legislation_finder_agent = _agent.build()
