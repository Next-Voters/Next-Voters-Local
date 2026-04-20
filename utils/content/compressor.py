"""Query-aware context compression via a Hugging Face-hosted scorer model.

Ports the core idea of LongLLMLingua — rank text segments by their
log-likelihood conditioned on the pipeline topic and drop the least relevant
ones — but runs the scorer model remotely through the Hugging Face Inference
Providers gateway instead of loading a multi-GB causal LM locally.

Flow per ``compress_text`` call:

1. Split the input into paragraph-sized segments.
2. Score each segment by its mean per-token log-likelihood under a small
   hosted LM, optionally conditioned on a ``query`` (the pipeline ``topic``).
3. Retain the highest-scoring segments until the target retention rate is met.
4. Reorder the kept segments so the most relevant ones sit at the first and
   last positions — a small mitigation for the "lost in the middle" effect.

Auth: ``HF_TOKEN``. Scorer model: ``HF_SCORER_MODEL``.
"""

import logging
import re
from typing import Optional

from config.constants import (
    COMPRESSION_RATE,
    HF_SCORER_MODEL,
    HF_SCORER_TIMEOUT_S,
    MIN_CHARS_TO_COMPRESS,
)
from utils.content.hf_scorer import HFScorerError, score_tokens

logger = logging.getLogger(__name__)

# Split on blank lines and runs of whitespace after a period. Works well for
# Tavily Extract + markdown.new output; degrades gracefully to sentence-ish
# boundaries when the source lacks clear paragraph breaks.
_SEGMENT_SPLIT_RE = re.compile(r"\n{2,}|(?<=[.!?])\s{2,}")

# Very short segments aren't worth a separate remote call — merge them into
# whichever neighbour they sit next to.
_MIN_SEGMENT_CHARS = 200

# Cap the characters sent to the HF scorer per segment. Hosted models have
# input token limits; truncating the tail keeps each call within budget while
# still giving the scorer enough context to rank reliably.
_MAX_SCORED_CHARS_PER_SEGMENT = 2_000


def _split_segments(text: str) -> list[str]:
    """Break *text* into paragraph-sized segments for independent scoring."""
    rough = _SEGMENT_SPLIT_RE.split(text)
    merged: list[str] = []
    buf = ""
    for seg in rough:
        seg = seg.strip()
        if not seg:
            continue
        if len(buf) + len(seg) < _MIN_SEGMENT_CHARS:
            buf = f"{buf}\n\n{seg}" if buf else seg
            continue
        if buf:
            merged.append(buf)
        buf = seg
    if buf:
        merged.append(buf)
    return merged or [text]


def _build_scoring_prompt(segment: str, query: Optional[str]) -> str:
    head = segment[:_MAX_SCORED_CHARS_PER_SEGMENT]
    if query:
        return f"Question: {query}\nContext: {head}"
    return head


def _score_segment(segment: str, query: Optional[str]) -> float:
    """Return the mean per-token log-likelihood of *segment* given *query*.

    Higher values mean the segment is more predictable under the scorer given
    the query context, which we treat as a proxy for topical relevance.
    ``float('-inf')`` is returned when scoring fails, so failed segments sort
    last (i.e. get dropped first).
    """
    prompt = _build_scoring_prompt(segment, query)
    try:
        logprobs = score_tokens(
            prompt, model=HF_SCORER_MODEL, timeout=HF_SCORER_TIMEOUT_S
        )
    except HFScorerError as exc:
        logger.warning("HF scoring failed: %s", exc)
        return float("-inf")

    # Drop the first token — its logprob is always the bootstrap placeholder.
    usable = [lp for lp in logprobs[1:] if lp != 0.0]
    if not usable:
        return float("-inf")
    return sum(usable) / len(usable)


def _reorder_for_edges(segments_in_rank_order: list[str]) -> list[str]:
    """Place the highest-ranked segments at the first and last positions.

    Example: ranks [A, B, C, D, E] (best → worst) become [A, C, E, D, B] —
    A and B at the edges, E (worst) in the middle.
    """
    n = len(segments_in_rank_order)
    if n < 2:
        return list(segments_in_rank_order)
    out: list[Optional[str]] = [None] * n
    front, back = 0, n - 1
    place_front = True
    for seg in segments_in_rank_order:
        if place_front:
            out[front] = seg
            front += 1
        else:
            out[back] = seg
            back -= 1
        place_front = not place_front
    return [s for s in out if s is not None]


def compress_text(
    text: str,
    rate: float = COMPRESSION_RATE,
    query: Optional[str] = None,
) -> str:
    """Compress *text* to retain the most relevant content given *query*.

    Args:
        text: Raw content to compress.
        rate: Target retention rate (``0.0`` = drop everything, ``1.0`` = keep all).
        query: Optional topic/question. When provided, segments are ranked by
            their log-likelihood conditioned on the query. When ``None``, they
            are ranked by unconditional log-likelihood.

    Returns:
        Compressed text composed of the highest-ranked segments, reordered so
        the most relevant ones appear at the edges. On scorer failure, falls
        back to a head truncation to ``rate * len(text)`` characters.
    """
    if not text or len(text) < MIN_CHARS_TO_COMPRESS:
        return text

    segments = _split_segments(text)
    if len(segments) <= 1:
        return text

    target_chars = max(MIN_CHARS_TO_COMPRESS, int(len(text) * rate))

    scored: list[tuple[str, float]] = []
    any_scored = False
    for seg in segments:
        score = _score_segment(seg, query)
        scored.append((seg, score))
        if score != float("-inf"):
            any_scored = True

    if not any_scored:
        logger.warning(
            "All %d segments failed HF scoring; falling back to head truncation.",
            len(segments),
        )
        return text[:target_chars]

    scored.sort(key=lambda pair: pair[1], reverse=True)

    kept: list[str] = []
    total = 0
    for seg, _ in scored:
        if kept and total + len(seg) > target_chars:
            continue
        kept.append(seg)
        total += len(seg)
        if total >= target_chars:
            break

    reordered = _reorder_for_edges(kept)
    compressed = "\n\n".join(reordered)
    logger.info(
        "HF LongLLMLingua: %d → %d chars (%.0f%% retained, %d/%d segments, query=%r)",
        len(text),
        len(compressed),
        100 * len(compressed) / max(len(text), 1),
        len(kept),
        len(segments),
        query,
    )
    return compressed
