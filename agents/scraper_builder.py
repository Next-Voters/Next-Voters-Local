import operator
from dotenv import load_dotenv

from typing import TypedDict, Annotated, NotRequired

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from utils.agents import should_continue

load_dotenv()

model = ChatOpenAI(model="gpt-4o", temperature=0.0, max_tokens=2000, timeout=30)


class ScraperBuilderState(TypedDict):
    """State for the scraper builder agent."""

    messages: Annotated[list[BaseMessage], operator.add]


# === TOOL LIST ===

tools = []


# === FUNCTIONS FOR NODES ===

def call_model(state: ScraperBuilderState) -> ScraperBuilderState:
    """Call the LLM with the current state."""
    messages = state["messages"]

    system_prompt = "You are a web scraper builder agent."

    model_with_tools = model.bind_tools(tools)

    response = model_with_tools.invoke(
        [{"role": "system", "content": system_prompt}] + messages
    )

    return {"messages": [response]}


process_tools = ToolNode(tools)


def build_scraper_builder_agent():
    """Build and return the compiled scraper builder agent graph.

    This is a low-level LangGraph ReAct agent that:
    1. Takes URLs and bill metadata as input
    2. Generates scraping code using code_generator tool
    3. Executes code using python_repl tool
    4. Filters results by date using date_filter tool
    5. Debugs issues using debugger tool
    6. Returns raw legislation text and vote records

    Returns:
        A compiled LangGraph that can be invoked with state.
    """

    graph = StateGraph(ScraperBuilderState)

    graph.add_node("call_model", call_model)
    graph.add_node("tool_node", process_tools)

    graph.add_edge(START, "call_model")
    graph.add_conditional_edges(
        "call_model",
        should_continue,
        {
            True: "tool_node",
            False: END,
        },
    )
    graph.add_edge("tool_node", "call_model")

    return graph.compile()


scraper_builder_agent = build_scraper_builder_agent()
