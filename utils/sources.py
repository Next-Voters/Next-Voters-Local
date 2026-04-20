"""Source-item normalization helpers.

Pipeline state carries legislation sources as a heterogeneous list of either
plain URL strings or pre-fetched dicts of the shape
``{"url": str, "content": str, "source": "pdf"}``. Multiple call sites need
to pull the URL (and sometimes a snippet) back out of that shape — this
module centralizes that access so the str/dict branching lives in one place.
"""

from __future__ import annotations

from typing import Any

SourceItem = str | dict[str, Any]

_SNIPPET_CHARS = 800


def extract_url_and_snippet(item: SourceItem) -> tuple[str, str]:
    """Return ``(url, snippet)`` for a source item.

    For dict items the snippet is the first ``_SNIPPET_CHARS`` of the
    pre-fetched ``content`` field (empty string if absent). For plain URL
    strings the snippet is always empty.
    """
    if isinstance(item, dict):
        url = str(item.get("url", "")).strip()
        snippet = (item.get("content") or "")[:_SNIPPET_CHARS]
        return url, snippet
    return str(item).strip(), ""
