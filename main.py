import httpx
from dotenv import load_dotenv

from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

from agents.legislation_finder import legislation_finder_agent

from utils.models import WriterOutput
from utils.typed_dicts import ChainData
from utils.prompts import writer_sys_prompt, note_taker_sys_prompt
from utils.cli_helpers import show_welcome, LOG

load_dotenv()

console = Console()
model = ChatOpenAI(model="gpt-4o-mini")

def run_legislation_finder(inputs: ChainData) -> ChainData:
    """Run the legislation finder agent as a node."""
    city = inputs.get("city", "Unknown")

    with console.status(f"[bold red]Searching for legislation in {city}..."):
        agent_result = legislation_finder_agent.invoke({"city": city})

    legislation_sources = agent_result.get("reliable_legislation_sources", [])

    messages = agent_result.get("messages", [])
    LOG(f"Agent steps: {len(messages)}", "dim")
    for msg in messages[-3:]:
        msg_type = type(msg).__name__
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_names = [tc.get("name", "unknown") for tc in msg.tool_calls]
            LOG(f"  → {msg_type}: {', '.join(tool_names)}", "yellow")
        elif msg_type == "ToolMessage":
            LOG(f"  → {msg_type}: {msg.name}", "green")
        elif msg_type == "AIMessage" and msg.content:
            content_preview = msg.content[:80].replace("\n", " ")
            LOG(f"  → {msg_type}: {content_preview}...", "dim")

    LOG(f"Found [green]{len(legislation_sources)}[/green] reliable sources", "green")
    return {**inputs, "legislation_sources": legislation_sources}


def run_content_retrieval(inputs: ChainData) -> ChainData:
    """Fetch content from legislation sources."""
    legislation_sources = inputs.get("legislation_sources", [])

    with console.status(
        f"[bold red]Fetching content from {len(legislation_sources)} sources..."
    ):
        legislation_content = []

        for source in legislation_sources:
            url = source.get("url") if isinstance(source, dict) else source

            if not url:
                legislation_content.append(f"[Invalid source: {source}]")
                continue

            try:
                markdown_url = f"https://markdown.new/{url}"
                response = httpx.get(markdown_url, timeout=30, follow_redirects=True)
                response.raise_for_status()
                legislation_content.append(response.text)
            except httpx.HTTPError as e:
                LOG(f"Failed to fetch: {url}", "red dim")
                legislation_content.append(f"[Failed to fetch: {url}]")

    LOG(f"Content retrieved: [green]{len(legislation_content)}[/green] items", "green")
    return {**inputs, "legislation_content": legislation_content}


def research_note_taker(inputs: ChainData) -> ChainData:
    raw_content_list = inputs.get("legislation_content", [])

    if not raw_content_list:
        return {**inputs, "notes": "No legislation content found."}

    raw_content = []

    for content in raw_content_list:
        raw_content.append(content + "\n")

    system_prompt = note_taker_sys_prompt.format(raw_content=raw_content)

    with console.status("[bold red]Analyzing legislation content..."):
        ai_generated_notes = model.invoke(
            [{"role": "system", "content": system_prompt}],
        )

    return {**inputs, "notes": str(ai_generated_notes.content)}


def research_summary_writer(inputs: ChainData) -> ChainData:
    """Generate final output using LLM with structured output."""
    notes = inputs.get("notes")
    LOG(f"Notes length: {len(notes) if notes else 0}", "red")

    system_prompt = writer_sys_prompt.format(notes=notes)

    structured_model = model.with_structured_output(WriterOutput)

    with console.status("[bold red]Generating legislation summary..."):
        ai_generated_summary: WriterOutput = structured_model.invoke(
            [{"role": "system", "content": system_prompt}],
        )

    LOG(
        f"Generated: {ai_generated_summary.title if ai_generated_summary else 'None'}",
        "green",
    )

    if ai_generated_summary is None:
        return {**inputs, "legislation_summary": None}

    title_lower = (
        ai_generated_summary.title.lower().strip() if ai_generated_summary.title else ""
    )
    no_title_patterns = ("no content", "no recent", "no legislation", "none", "")

    if (
        title_lower in no_title_patterns
        or title_lower.startswith("no ")
        or title_lower.startswith("n/a")
    ):
        LOG("No valid legislation found - filtering out", "yellow")
        return {**inputs, "legislation_summary": None}

    return {**inputs, "legislation_summary": ai_generated_summary}


def run_politician_public_statement(inputs: ChainData) -> ChainData:
    """Run the politican public statement finder agent as a node."""
    return {**inputs, "politician_public_statements": []}


def report_formatter(inputs: ChainData) -> ChainData:
    """Format a final report using the legislative summary and the politician public statements."""
    legislation_summary = inputs.get("legislation_summary")
    public_statements = inputs.get("politician_public_statements")

    if legislation_summary is None:
        return {
            **inputs,
            "markdown_report": "# No Legislation Found\n\nNo recent legislation was found for the specified city. Try a different city or check back later for updates.",
        }

    lines = [
        f"# {legislation_summary.title}",
        "",
        "## Summary",
        "",
        legislation_summary.summary,
        "",
        "## Full Report",
        "",
        legislation_summary.body,
        "",
        "---",
        "",
        "## Politician Public Statements",
        "### Coming Soon!",
        "",
    ]

    for politician in public_statements:
        lines.append(f"### {politician['name']}")
        lines.append("")
        for statement in politician["statement_summaries"]:
            lines.append(f"**Legislation Source Link:** {statement['source']}")
            lines.append("")
            lines.append(statement["summary"])
            lines.append("")

    markdown_report = "\n".join(lines)

    return {**inputs, "markdown_report": markdown_report}


chain = (
    RunnableLambda(run_legislation_finder)
    | RunnableLambda(run_content_retrieval)
    | RunnableLambda(research_note_taker)
    | RunnableLambda(research_summary_writer)
    | RunnableLambda(run_politician_public_statement)
    | RunnableLambda(report_formatter)
)


# Run CLI app
if __name__ == "__main__":
    show_welcome()

    city = input("\n➜ Enter city name: ")

    console.print()
    result = chain.invoke({"city": city})

    report = result.get("markdown_report")

    console.print()
    console.print(
        Panel.fit(
            "[bold red]NV Local Results[/bold red]",
            border_style="red",
            box=box.DOUBLE,
        )
    )
    console.print()
    console.print(Markdown(report))
