"""
Embedding via HuggingFace Inference API.
Zero local RAM — same multilingual model, runs server-side on HF.
Requires HF_TOKEN env var (free at https://huggingface.co/settings/tokens).
"""

import logging
from functools import lru_cache

import httpx

from app.config import get_settings

logger = logging.getLogger("agent-service.memory.embeddings")

HF_ROUTER = "https://router.huggingface.co/hf-inference/models/{model}"

EMBEDDING_DIM = 384

_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        settings = get_settings()
        headers = {}
        if settings.hf_token:
            headers["Authorization"] = f"Bearer {settings.hf_token}"
        _http_client = httpx.Client(timeout=30, headers=headers)
    return _http_client


def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    url = HF_ROUTER.format(model=settings.embedding_model)
    client = _get_http_client()

    resp = client.post(url, json={"inputs": texts, "options": {"wait_for_model": True}})
    resp.raise_for_status()
    vectors = resp.json()

    if isinstance(vectors[0], list) and isinstance(vectors[0][0], list):
        return [v[0] for v in vectors]
    return vectors


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]


@lru_cache(maxsize=1)
def get_embedding_dimension() -> int:
    return EMBEDDING_DIM
