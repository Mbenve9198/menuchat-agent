"""
Contact memory — per-lead observations persisted across agent sessions.

Stores the agent's own interpretive memory about each lead:
  - What the agent observed about the lead's personality, concerns, preferences
  - Which strategy was used and how it went
  - Key details that should inform future interactions

This is different from CRM data (factual: calls, messages) — this is the
agent's OWN understanding of the relationship.
"""

import logging
from datetime import datetime, timezone

from app.memory.embeddings import embed_single
from app.memory.qdrant_store import (
    CONTACT_MEMORIES,
    scroll_by_filter,
    search_similar,
    upsert_point,
)

logger = logging.getLogger("agent-service.memory.contact")

MAX_MEMORIES_PER_CONTACT = 10
DEDUP_SIMILARITY_THRESHOLD = 0.92


async def store_observation(
    contact_email: str,
    observation: str,
    strategy_used: str = "",
    outcome: str = "",
    conversation_id: str = "",
    task_type: str = "",
) -> str:
    """
    Store an agent observation about a specific contact.
    Deduplicates by checking if a very similar observation already exists.
    Enforces a max-memories-per-contact limit.
    """
    vector = embed_single(f"{contact_email} {observation}")

    payload = {
        "contact_email": contact_email,
        "observation": observation,
        "strategy_used": strategy_used,
        "outcome": outcome,
        "conversation_id": conversation_id,
        "task_type": task_type,
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        existing = search_similar(
            CONTACT_MEMORIES,
            query_vector=vector,
            limit=1,
            score_threshold=DEDUP_SIMILARITY_THRESHOLD,
            filters={"contact_email": contact_email},
        )
        if existing:
            existing_id = existing[0]["id"]
            logger.info(
                "Dedup: updating existing memory %s for %s (similarity=%.3f)",
                existing_id, contact_email, existing[0].get("score", 0),
            )
            point_id = upsert_point(CONTACT_MEMORIES, vector, payload, point_id=existing_id)
            return point_id
    except Exception as e:
        logger.warning("Dedup check failed, inserting new: %s", e)

    point_id = upsert_point(CONTACT_MEMORIES, vector, payload)
    logger.info("Stored contact memory for %s: %s... (id=%s)", contact_email, observation[:60], point_id)

    try:
        _enforce_memory_limit(contact_email)
    except Exception as e:
        logger.warning("Memory limit enforcement failed: %s", e)

    return point_id


def _enforce_memory_limit(contact_email: str):
    """Remove oldest memories if a contact exceeds the limit."""
    all_mems = scroll_by_filter(
        CONTACT_MEMORIES,
        filters={"contact_email": contact_email},
        limit=MAX_MEMORIES_PER_CONTACT + 10,
    )

    if len(all_mems) <= MAX_MEMORIES_PER_CONTACT:
        return

    all_mems.sort(key=lambda r: r.get("stored_at", ""), reverse=True)
    to_remove = all_mems[MAX_MEMORIES_PER_CONTACT:]

    from app.memory.qdrant_store import get_qdrant_client, _collection_name
    client = get_qdrant_client()
    ids_to_delete = [m["id"] for m in to_remove]
    from qdrant_client.models import PointIdsList
    client.delete(
        collection_name=_collection_name(CONTACT_MEMORIES),
        points_selector=PointIdsList(points=ids_to_delete),
    )
    logger.info("Pruned %d old memories for %s", len(ids_to_delete), contact_email)


async def recall_contact_history(contact_email: str, limit: int = 10) -> list[dict]:
    """
    Retrieve all agent observations for a specific contact.
    Returns list of observations sorted by storage time.
    """
    results = scroll_by_filter(
        CONTACT_MEMORIES,
        filters={"contact_email": contact_email},
        limit=limit,
    )

    results.sort(key=lambda r: r.get("stored_at", ""), reverse=True)

    logger.info("Recalled %d memories for %s", len(results), contact_email)
    return results
