from langchain_core.runnables import RunnableLambda

from utils.schemas import ChainData
from utils.async_runner import run_async


def run_politician_commentary_finder(inputs: ChainData) -> ChainData:
    from agents.political_commentary_finder import political_commentary_agent

    city = inputs.get("city", "Unknown")

    agent_result = run_async(lambda: political_commentary_agent.ainvoke({"city": city}))

    political_commentary = agent_result.get("political_commentary", [])

    return {**inputs, "politician_public_statements": political_commentary}


politician_commentary_chain = RunnableLambda(run_politician_commentary_finder)
