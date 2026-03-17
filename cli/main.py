"""Command-line interface for NV Local voter education tool.

This module provides the CLI entry point using Rich for formatted console output.
It system_prompts the user for a city name, invokes the pipeline, and displays the
resulting markdown report in a formatted panel.

Key function:
    main: Displays welcome message, collects city input, runs pipeline, and
          renders the markdown report.
"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

from pipelines.nv_local import chain
from utils.cli import show_welcome

console = Console()


def main():
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


if __name__ == "__main__":
    main()
