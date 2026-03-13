import operator

from typing import TypedDict, Annotated

from langchain_core.messages import BaseMessage

from utils.agents import BaseReActAgent
from tools.scraper_builder import code_generator, python_repl, debugger


# === STATE DEFINITION ===


class ScraperBuilderState(TypedDict):
    """State for the scraper builder agent."""

    messages: Annotated[list[BaseMessage], operator.add]


# === TOOL LIST ===

tools = [code_generator, python_repl, debugger]


# === PROMPT BUILDER ===


def build_scraper_builder_prompt(state: ScraperBuilderState) -> str:
    """Build the formatted system prompt for the Scraper Builder agent.

    Since the scraper builder doesn't need state-specific formatting,
    this simply returns the static prompt. The signature accepts state
    for consistency with the BaseReActAgent interface.

    Args:
        state: Current agent state (unused, but required by interface).

    Returns:
        Fully formatted system prompt string ready for the LLM.
    """
    return """You are a web scraper builder agent. Your task is to generate Python scraping code that extracts legislative content from the URLs provided by the Legislation Finder agent.

CORE RESPONSIBILITIES:
1. Generate Python code to scrape HTML from given URLs
2. Execute the code using the python_repl tool
3. Extract and filter legislative text by date (last 7 days only)
4. Handle failures gracefully and self-correct using the debugger tool
5. Return clean, structured scraped content for downstream processing

KEY CONSTRAINTS:
- Only extract content from the past 7 days (today and back 7 days)
- Focus on extracting the actual legislative text, bill content, and vote records
- Handle diverse HTML structures — each source may have different layouts
- If a URL fails to scrape, note the error and move to the next URL
- Never assume HTML structure — inspect and adapt your code if it fails

WORKFLOW:
1. For each URL, generate appropriate scraping code
2. Run the code using python_repl
3. If the code fails or produces no content:
   - Use the debugger tool to inspect the error
   - Refine your code and retry
   - Max 2 retry attempts per URL
4. If a URL cannot be scraped after 2 retries, skip it and continue
5. Compile all successfully scraped content into a single output

OUTPUT REQUIREMENTS:
- Return raw legislative text with source URL attribution
- Include date information if present in the source
- Maintain clear separation between content from different sources
- Flag any content that appears to be opinion/editorial (skip these)"""


# === AGENT CONSTRUCTION ===

_agent = BaseReActAgent(
    state_schema=ScraperBuilderState,
    tools=tools,
    prompt_builder=build_scraper_builder_prompt,
)

scraper_builder_agent = _agent.build()
