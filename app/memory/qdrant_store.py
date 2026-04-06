"""
Qdrant vector store — manages collections and CRUD operations.
Two collections:
  - episodes: cross-lead learning from human feedback
  - contact_memories: per-lead observations from each agent run
"""

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.memory.embeddings import get_embedding_dimension

logger = logging.getLogger("agent-service.memory.qdrant")

_client: QdrantClient | None = None


def _collection_name(name: str) -> str:
    prefix = get_settings().qdrant_collection_prefix
    return f"{prefix}_{name}"


EPISODES = "episodes"
CONTACT_MEMORIES = "contact_memories"


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        settings = get_settings()
        api_key = settings.qdrant_api_key or None
        _client = QdrantClient(url=settings.qdrant_url, api_key=api_key)
        logger.info("Qdrant client connected: %s", settings.qdrant_url)
    return _client


async def init_collections():
    """Create collections if they don't exist. Called at startup."""
    client = get_qdrant_client()
    dim = get_embedding_dimension()

    for name in [EPISODES, CONTACT_MEMORIES]:
        col = _collection_name(name)
        existing = [c.name for c in client.get_collections().collections]
        if col not in existing:
            client.create_collection(
                collection_name=col,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection: %s (dim=%d)", col, dim)
        else:
            logger.info("Qdrant collection exists: %s", col)


def upsert_point(collection: str, vector: list[float], payload: dict, point_id: str | None = None) -> str:
    client = get_qdrant_client()
    pid = point_id or uuid.uuid4().hex
    client.upsert(
        collection_name=_collection_name(collection),
        points=[PointStruct(id=pid, vector=vector, payload=payload)],
    )
    return pid


def search_similar(
    collection: str,
    query_vector: list[float],
    limit: int = 3,
    score_threshold: float = 0.3,
    filters: dict[str, Any] | None = None,
) -> list[dict]:
    client = get_qdrant_client()
    qdrant_filter = None
    if filters:
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filters.items()
        ]
        qdrant_filter = Filter(must=conditions)

    results = client.query_points(
        collection_name=_collection_name(collection),
        query=query_vector,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=qdrant_filter,
    ).points

    return [
        {"id": r.id, "score": r.score, **r.payload}
        for r in results
    ]


def scroll_by_filter(collection: str, filters: dict[str, Any], limit: int = 20) -> list[dict]:
    client = get_qdrant_client()
    conditions = [
        FieldCondition(key=k, match=MatchValue(value=v))
        for k, v in filters.items()
    ]

    results, _ = client.scroll(
        collection_name=_collection_name(collection),
        scroll_filter=Filter(must=conditions),
        limit=limit,
    )

    return [{"id": r.id, **r.payload} for r in results]


def close_qdrant():
    global _client
    if _client:
        _client.close()
    _client = None
