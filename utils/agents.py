"""Shared utilities for LangGraph ReAct agents."""

from typing import TypeVar, Callable

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# Generic state type for type hints
StateType = TypeVar("StateType")


class BaseReActAgent:
    """Base class for ReAct agents with customizable state, tools, and dynamic prompts.

    This class encapsulates the core ReAct loop logic:
    1. Call model with dynamically built system prompt and messages
    2. If model returns tool calls, execute them
    3. Loop back to model with tool results
    4. End when model returns no tool calls

    Instances customize:
    - State schema (TypedDict)
    - Tools list
    - Prompt builder (function that takes state and returns formatted system prompt)
    """

    def __init__(
        self,
        state_schema: type,
        tools: list,
        prompt_builder: Callable[[StateType], str],
        # Optional
        model_name: str = "gpt-4o",
        temperature: float = 0.0,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """Initialize the ReAct agent.

        Args:
            state_schema: A TypedDict class defining the agent's state structure.
                          Must include 'messages' key with Annotated[list[BaseMessage], operator.add].
            tools: List of LangChain tools the agent can use.
            prompt_builder: A callable that takes the current state and returns a formatted
                           system prompt string. This is invoked on each model call to ensure
                           the prompt reflects the current state (e.g., updated reflections).

            model_name: OpenAI model name.
            temperature: Model temperature.
            max_tokens: Maximum tokens for model response.
            timeout: Request timeout in seconds.
        """
        self.state_schema = state_schema
        self.tools = tools
        self.prompt_builder = prompt_builder

        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def _should_continue(self, state: StateType) -> bool:
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

    def _call_model(self, state: StateType) -> dict:
        """Call the LLM with the current state and dynamically built system prompt.

        The system prompt is built fresh on each invocation using the prompt_builder
        callback, ensuring it reflects the current state (e.g., updated reflections).

        Args:
            state: Current agent state.

        Returns:
            Dict with 'messages' key containing the model response.
        """

        messages = state["messages"]
        system_prompt = self.prompt_builder(state)
        model_with_tools = self.model.bind_tools(self.tools)

        response = model_with_tools.invoke(
            [{"role": "system", "content": system_prompt}] + messages
        )

        return {"messages": [response]}

    def build(self):
        """Build and compile the agent graph.

        Returns:
            A compiled LangGraph that can be invoked with state.
        """

        tool_node = ToolNode(self.tools)

        graph = StateGraph(self.state_schema)
        graph.add_node("call_model", self._call_model)
        graph.add_node("tool_node", tool_node)

        graph.add_edge(START, "call_model")
        graph.add_conditional_edges(
            "call_model",
            self._should_continue,
            {
                True: "tool_node",
                False: END,
            },
        )
        graph.add_edge("tool_node", "call_model")

        return graph.compile()
