"""Query-aware context compression via Microsoft's LongLLMLingua.

Thin wrapper around ``llmlingua.PromptCompressor`` running the LongLLMLingua
ranking algorithm locally with a small causal LM (``Qwen/Qwen2.5-0.5B``).

Segments are ranked by question-aware perplexity and reordered so the most
relevant content lands at the first and last positions — a mitigation for the
long-context "lost in the middle" effect. Model weights (~1 GB) download once
on first invocation and stay resident for the life of the process.
"""

import logging
from typing import Optional

from llmlingua import PromptCompressor

from config.constants import COMPRESSION_RATE, MIN_CHARS_TO_COMPRESS

logger = logging.getLogger(__name__)

# Small causal LM used for segment scoring. 0.5B params keeps CPU-only runs
# tractable; the LongLLMLingua algorithm is scorer-agnostic, so model choice
# trades ranking accuracy against weight/memory.
_SCORER_MODEL = "Qwen/Qwen2.5-0.5B"

_compressor: Optional[PromptCompressor] = None


def _get_compressor() -> PromptCompressor:
    """Lazily instantiate the shared PromptCompressor on first use."""
    global _compressor
    if _compressor is None:
        _compressor = PromptCompressor(
            model_name=_SCORER_MODEL,
            use_llmlingua2=False,
            device_map="cpu",
        )
    return _compressor


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
            question-aware perplexity. When ``None``, falls back to
            unconditional ranking.

    Returns:
        The compressed prompt. On any compressor failure, falls back to a head
        truncation at ``rate * len(text)`` characters so the pipeline never
        empties out.
    """
    if not text or len(text) < MIN_CHARS_TO_COMPRESS:
        return text

    try:
        result = _get_compressor().compress_prompt(
            [text],
            question=query or "",
            rate=rate,
            rank_method="longllmlingua",
            reorder_context="sort",
        )
        compressed = result.get("compressed_prompt", text)
    except Exception as exc:
        logger.warning(
            "LongLLMLingua failed (%s); falling back to head truncation.", exc
        )
        target_chars = max(MIN_CHARS_TO_COMPRESS, int(len(text) * rate))
        return text[:target_chars]

    logger.info(
        "LongLLMLingua: %d → %d chars (%.0f%% retained, query=%r)",
        len(text),
        len(compressed),
        100 * len(compressed) / max(len(text), 1),
        query,
    )
    return compressed
