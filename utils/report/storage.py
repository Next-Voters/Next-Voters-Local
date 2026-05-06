"""Save pipeline reports to the Supabase reports table."""

import logging
from datetime import date
from typing import Any

from utils.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Module-level cache: topic_name -> topic_id
_topic_ids: dict[str, int] = {}


def _get_topic_id(topic_name: str) -> int | None:
    """Resolve a topic name to its integer ID, caching the result."""
    if topic_name in _topic_ids:
        return _topic_ids[topic_name]

    try:
        client = get_supabase_client()
        response = (
            client.table("supported_topics")
            .select("topic_id")
            .eq("topic_name", topic_name)
            .limit(1)
            .execute()
        )
        if response.data:
            tid = response.data[0]["topic_id"]
            _topic_ids[topic_name] = tid
            return tid
        logger.warning(f"No topic_id found for topic: {topic_name}")
        return None
    except Exception as e:
        logger.error(f"Failed to resolve topic_id for {topic_name}: {e}")
        return None


def save_report(
    city: str,
    topic_name: str,
    items: list[dict[str, str]],
    sources: list[str],
) -> bool:
    """Upsert a single report into the reports table.

    Args:
        city: City name (FK to supported_cities).
        topic_name: Topic name string (resolved to topic_id).
        items: List of legislation item dicts, each {"header": ..., "description": ...}.
        sources: List of source URL strings.

    Returns:
        True on success, False on failure.
    """
    topic_id = _get_topic_id(topic_name)
    if topic_id is None:
        return False

    try:
        client = get_supabase_client()
        client.table("reports").upsert(
            {
                "city": city,
                "topic_id": topic_id,
                "report_date": date.today().isoformat(),
                "items": items,
                "sources": sources,
            },
            on_conflict="city,topic_id,report_date",
        ).execute()
        logger.info(f"Saved report: {city}/{topic_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to save report {city}/{topic_name}: {e}")
        return False


def save_all(results: dict[tuple[str, str], dict[str, Any]]) -> int:
    """Save all pipeline results to the reports table.

    Args:
        results: Pipeline results keyed by (city, topic) tuple.
                 Each value should contain 'legislation_summary' (WriterOutput)
                 and 'legislation_sources' (list of URLs or dicts).

    Returns:
        Number of successfully saved reports.
    """
    saved = 0

    for (city, topic), result in results.items():
        if result.get("error"):
            continue

        summary = result.get("legislation_summary")
        if summary is None:
            continue

        items = [
            {"header": item.header, "description": item.description}
            for item in summary.items
        ]

        raw_sources = result.get("legislation_sources") or []
        sources = [
            s["url"] if isinstance(s, dict) else s
            for s in raw_sources
            if s
        ]

        if save_report(city, topic, items, sources):
            saved += 1

    logger.info(f"Saved {saved} reports to database")
    return saved
