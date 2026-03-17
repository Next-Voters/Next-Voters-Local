"""CLI wrapper script for NV Local voter education tool.

This module is a simple entry point script that runs the CLI main function.
It displays the welcome message, system_prompts for city input, executes the pipeline,
and renders the resulting markdown report.

Usage:
    python run_cli_main.py

This script is an alternative to running `python -m cli.main`.
"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

from pipelines.nv_local import chain
from utils.cli import show_welcome, LOG

console = Console()

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
