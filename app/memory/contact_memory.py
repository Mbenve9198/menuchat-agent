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
from app.memory.qdrant_store import CONTACT_MEMORIES, scroll_by_filter, upsert_point

logger = logging.getLogger("agent-service.memory.contact")


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
    Called at the end of each agent run.
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

    point_id = upsert_point(CONTACT_MEMORIES, vector, payload)
    logger.info("Stored contact memory for %s: %s... (id=%s)", contact_email, observation[:60], point_id)
    return point_id


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
