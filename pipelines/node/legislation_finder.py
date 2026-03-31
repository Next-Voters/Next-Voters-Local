from langchain_core.runnables import RunnableLambda

from utils.schemas import ChainData
from utils.async_runner import run_async


def run_legislation_finder(inputs: ChainData) -> ChainData:
    from agents.legislation_finder import legislation_finder_agent

    city = inputs.get("city", "Unknown")

    agent_result = run_async(lambda: legislation_finder_agent.ainvoke({"city": city}))

    legislation_sources = agent_result.get("reliable_legislation_sources", [])

    return {**inputs, "legislation_sources": legislation_sources}


legislation_finder_chain = RunnableLambda(run_legislation_finder)
