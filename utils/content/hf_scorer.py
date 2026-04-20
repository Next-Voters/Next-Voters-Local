"""Hugging Face Inference-backed token scorer for query-aware compression.

Uses the HF Inference Providers gateway (``huggingface_hub.InferenceClient``) to
obtain per-token prefill logprobs from a small hosted causal LM. Auth is via the
``HF_TOKEN`` environment variable; HF routes and bills centrally, so no
provider-specific keys are required.
"""

import logging
import os
from functools import lru_cache

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)


class HFScorerError(RuntimeError):
    """Raised when HF scoring fails or is misconfigured."""


@lru_cache(maxsize=4)
def _get_client(model: str, timeout: float) -> InferenceClient:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise HFScorerError(
            "HF_TOKEN environment variable is required for Hugging Face-backed "
            "compression. Set it in your .env to a token with Inference API read access."
        )
    return InferenceClient(model=model, token=token, timeout=timeout)


def score_tokens(text: str, model: str, timeout: float = 30.0) -> list[float]:
    """Return per-token prefill logprobs for *text* from the configured scorer.

    The first token's logprob is always ``0.0`` (no preceding context to condition on);
    remaining tokens carry the logprob returned by the provider.

    Raises ``HFScorerError`` when ``HF_TOKEN`` is unset, the network call fails, or
    the chosen provider does not return prefill logprobs (i.e. does not honour
    ``decoder_input_details=True``).
    """
    if not text:
        return []

    client = _get_client(model, timeout)

    try:
        response = client.text_generation(
            text,
            max_new_tokens=1,
            details=True,
            decoder_input_details=True,
            return_full_text=False,
        )
    except Exception as e:
        raise HFScorerError(f"HF Inference call failed for model {model!r}: {e}") from e

    details = getattr(response, "details", None)
    prefill = getattr(details, "prefill", None) if details is not None else None
    if not prefill:
        raise HFScorerError(
            f"Model {model!r} did not return prefill logprobs. The chosen provider "
            "may not support decoder_input_details=True; pick a different scorer "
            "model backed by Text Generation Inference."
        )

    logprobs: list[float] = []
    for token in prefill:
        logprob = getattr(token, "logprob", None)
        logprobs.append(float(logprob) if logprob is not None else 0.0)
    return logprobs
