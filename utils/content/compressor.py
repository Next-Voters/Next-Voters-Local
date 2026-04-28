"""Context compression via Microsoft's LLMLingua.

Thin wrapper around ``llmlingua.PromptCompressor`` running the base LLMLingua
ranking algorithm locally with a small causal LM (``Qwen/Qwen2.5-0.5B``).

Segments are ranked by perplexity and the least informative ones are dropped
until the retention rate is met. Model weights (~1 GB) download once on first
invocation and stay resident for the life of the process.
"""

import logging
from typing import Optional

from llmlingua import PromptCompressor

from config.constants import COMPRESSION_RATE, MIN_CHARS_TO_COMPRESS

logger = logging.getLogger(__name__)

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
    """Compress *text* to retain the most informative content.

    Args:
        text: Raw content to compress.
        rate: Target retention rate (``0.0`` = drop everything, ``1.0`` = keep all).
        query: Optional topic/question. Currently unused (reserved for future
            query-aware ranking).

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
            rate=rate,
            rank_method="llmlingua",
        )
        compressed = result.get("compressed_prompt", text)
    except Exception as exc:
        logger.warning(
            "LLMLingua failed (%s); falling back to head truncation.", exc
        )
        target_chars = max(MIN_CHARS_TO_COMPRESS, int(len(text) * rate))
        return text[:target_chars]

    logger.info(
        "LLMLingua: %d → %d chars (%.0f%% retained)",
        len(text),
        len(compressed),
        100 * len(compressed) / max(len(text), 1),
    )
    return compressed
