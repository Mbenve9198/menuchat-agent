"""
Embedding via Hugging Face Inference Providers (feature_extraction).

Richiede HF_TOKEN con permesso «Make calls to Inference Providers» (token fine-grained):
https://huggingface.co/settings/tokens
"""

from __future__ import annotations

import logging
from functools import lru_cache

from huggingface_hub import InferenceClient

from app.config import get_settings

logger = logging.getLogger("agent-service.memory.embeddings")

EMBEDDING_DIM = 384

_inference_client: InferenceClient | None = None


def _get_inference_client() -> InferenceClient:
    global _inference_client
    if _inference_client is None:
        settings = get_settings()
        token = (settings.hf_token or "").strip()
        if not token:
            raise RuntimeError(
                "HF_TOKEN non configurato. Crea un token su "
                "https://huggingface.co/settings/tokens con permesso "
                "«Make calls to Inference Providers», poi imposta HF_TOKEN su Render."
            )
        _inference_client = InferenceClient(token=token)
    return _inference_client


def _vector_to_list(arr) -> list[float]:
    """Normalizza output di feature_extraction (ndarray 1D/2D o liste annidate) in list[float]."""
    if hasattr(arr, "shape"):
        if len(arr.shape) == 2:
            arr = arr[0]
        return [float(x) for x in arr.ravel()]
    if isinstance(arr, list):
        if arr and isinstance(arr[0], list):
            return [float(x) for x in arr[0]]
        return [float(x) for x in arr]
    raise TypeError(f"Unexpected embedding type: {type(arr)}")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    model = settings.embedding_model
    client = _get_inference_client()
    out: list[list[float]] = []
    for t in texts:
        arr = client.feature_extraction(t, model=model)
        out.append(_vector_to_list(arr))
    return out


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]


@lru_cache(maxsize=1)
def get_embedding_dimension() -> int:
    return EMBEDDING_DIM
