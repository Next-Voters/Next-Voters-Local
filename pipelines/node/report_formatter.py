from langchain_core.runnables import RunnableLambda

from utils.schemas import ChainData


def _safe_text(value: object, fallback: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        return text or fallback
    return fallback


def report_formatter(inputs: ChainData) -> ChainData:
    legislation_summary = inputs.get("legislation_summary")

    if legislation_summary is None:
        return {
            **inputs,
            "markdown_report": "# No Legislation Found\n\nNo recent legislation was found for the specified city. Try a different city or check back later for updates.",
        }

    title = _safe_text(legislation_summary.title, "Untitled Report")
    summary = _safe_text(legislation_summary.summary, "No summary available.")
    body = _safe_text(legislation_summary.body, "No detailed report available.")

    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Full Report",
        "",
        body,
        "",
    ]

    raw_sources = inputs.get("legislation_sources") or []
    source_urls = [
        s["url"] if isinstance(s, dict) else s
        for s in raw_sources
        if s
    ]
    if source_urls:
        lines.append("## Sources")
        lines.append("")
        for i, url in enumerate(source_urls, start=1):
            lines.append(f"{i}. {url}")
        lines.append("")

    markdown_report = "\n".join(lines)

    return {**inputs, "markdown_report": markdown_report}


report_formatter_chain = RunnableLambda(report_formatter)
