"""
Embedding model for memory vector search.
Uses fastembed with a multilingual model for Italian + English support.
"""

import logging
from functools import lru_cache

from fastembed import TextEmbedding

from app.config import get_settings

logger = logging.getLogger("agent-service.memory.embeddings")

_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        settings = get_settings()
        logger.info("Loading embedding model: %s", settings.embedding_model)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _model = TextEmbedding(model_name=settings.embedding_model)
        logger.info("Embedding model loaded")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]


@lru_cache(maxsize=1)
def get_embedding_dimension() -> int:
    return len(embed_single("dimension probe"))
