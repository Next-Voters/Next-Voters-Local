"""
Global reports dictionary builder for the NV Local system.

This module is responsible for aggregating markdown reports from all city
pipelines into a single global dictionary that is used by the email dispatcher
and other system components that need access to city-specific reports.

The global reports dictionary is a fundamental piece of system-wide data
that flows from pipeline execution to subscriber notification.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_city_reports_dict(results: dict[str, dict[str, Any]]) -> dict[str, str]:
    """
    Extract markdown reports from pipeline results into a global dictionary.

    This function aggregates reports from all city pipeline executions into
    a single dictionary keyed by city name. This allows downstream components
    (like the email dispatcher) to quickly access reports for any city.

    Behavior with empty/missing reports:
    - Cities without a "markdown_report" key are skipped
    - Cities with empty string reports are skipped
    - Cities with errors in their results are skipped
    - The returned dictionary only contains cities with non-empty markdown reports

    Args:
        results: Pipeline results indexed by city
                {
                    "Toronto": {"markdown_report": "...", ...},
                    "New York City": {"markdown_report": "...", ...},
                    "Failed City": {"error": "...", "markdown_report": ""},
                    ...
                }

    Returns:
        Global reports dictionary mapping city names to markdown content.
        May be empty if no results have valid markdown_report values.
        {
            "Toronto": "# Toronto Report...",
            "New York City": "# NYC Report...",
            ...
        }
    """
    reports_by_city = {
        city: result.get("markdown_report", "")
        for city, result in results.items()
        if result.get("markdown_report")  # Only include successful reports
    }

    logger.info(f"Built reports dictionary for {len(reports_by_city)} cities")

    return reports_by_city
