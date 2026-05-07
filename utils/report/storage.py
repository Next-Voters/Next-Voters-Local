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


def save_report(city: str, topic_name: str, result: dict[str, Any]) -> bool:
    """Extract structured items from a pipeline result and upsert to the reports table.

    Args:
        city: City name (FK to supported_cities).
        topic_name: Topic name string (resolved to topic_id).
        result: Pipeline result dict containing 'legislation_summary' (WriterOutput).

    Returns:
        True on success, False on failure.
    """
    summary = result.get("legislation_summary")
    if summary is None:
        return False

    items = [
        {"header": item.header, "description": item.description}
        for item in summary.items
    ]

    if not items:
        logger.warning(f"No items to save for {city}/{topic_name}, skipping upsert")
        return False

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
            },
            on_conflict="city,topic_id,report_date",
        ).execute()
        logger.info(f"Saved report: {city}/{topic_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to save report {city}/{topic_name}: {e}")
        return False
