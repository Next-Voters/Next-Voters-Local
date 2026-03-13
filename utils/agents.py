"""Shared utilities for LangGraph ReAct agents."""

from typing import TypeVar

# Generic state type for type hints
StateType = TypeVar("StateType")


def should_continue(state: StateType) -> bool:
    """Determine if the agent should continue or end based on if there is a tool call to be made.

    This is a reusable function for ReAct agents that checks the last message
    for tool calls to determine if the agentic loop should continue.

    Args:
        state: The agent state with a 'messages' key

    Returns:
        bool: True if there are tool calls to process, False otherwise
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return True

    return False
