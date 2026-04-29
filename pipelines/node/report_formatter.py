from langchain_core.runnables import RunnableLambda

from utils.schemas import ChainData


def report_formatter(inputs: ChainData) -> ChainData:
    """Format legislation items into topic-organized markdown."""
    legislation_summary = inputs.get("legislation_summary")
    topic = inputs.get("topic", "General")
    city = inputs.get("city", "")

    if legislation_summary is None:
        return {
            **inputs,
            "markdown_report": "",
        }

    lines = [f"## {topic.upper()}", ""]

    for item in legislation_summary.items:
        lines.append(f"**{item.header}**")
        lines.append("")
        lines.append(item.description)
        lines.append("")

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
