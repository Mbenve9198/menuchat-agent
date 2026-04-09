"""
Memory Manager — orchestrates episodic and contact memory.

Provides high-level functions used by graph nodes:
  - recall_all(): fetch both episodic + contact memories for a run
  - store_run_memory(): save contact observation after a run completes
  - store_feedback(): save a human feedback episode
  - consolidate_contact_memories(): periodic job to compress old memories
"""

import json
import logging

import anthropic

from app.config import get_settings
from app.memory.episodic import recall_similar_episodes, store_episode
from app.memory.contact_memory import recall_contact_history, store_observation
from app.memory.embeddings import embed_single
from app.memory.qdrant_store import (
    CONTACT_MEMORIES,
    scroll_by_filter,
    upsert_point,
    get_qdrant_client,
    _collection_name,
)

logger = logging.getLogger("agent-service.memory.manager")

CONSOLIDATION_THRESHOLD = 5


async def recall_all(
    contact_email: str,
    context: dict,
    episodic_top_k: int = 3,
    contact_limit: int = 10,
) -> dict:
    """
    Retrieve all relevant memories for a run.

    Returns:
        {
            "episodic_examples": [...],  # similar past episodes
            "contact_memories": [...],   # observations about this lead
        }
    """
    episodic = []
    contact_mems = []

    try:
        episodic = await recall_similar_episodes(context, top_k=episodic_top_k)
    except Exception as e:
        logger.warning("Episodic recall failed (non-blocking): %s", e)

    try:
        contact_mems = await recall_contact_history(contact_email, limit=contact_limit)
    except Exception as e:
        logger.warning("Contact memory recall failed (non-blocking): %s", e)

    logger.info(
        "Memory recall complete: %d episodes, %d contact memories for %s",
        len(episodic), len(contact_mems), contact_email,
    )

    return {
        "episodic_examples": episodic,
        "contact_memories": contact_mems,
    }


async def store_run_memory(
    contact_email: str,
    observation: str,
    strategy_used: str = "",
    outcome: str = "",
    conversation_id: str = "",
    task_type: str = "",
) -> str | None:
    """Store the agent's observation about a contact after a run."""
    if not observation or not contact_email:
        return None
    try:
        return await store_observation(
            contact_email=contact_email,
            observation=observation,
            strategy_used=strategy_used,
            outcome=outcome,
            conversation_id=conversation_id,
            task_type=task_type,
        )
    except Exception as e:
        logger.warning("store_run_memory failed (non-blocking): %s", e)
        return None


async def store_feedback(episode: dict) -> str | None:
    """Store a human feedback episode for future learning."""
    try:
        return await store_episode(episode)
    except Exception as e:
        logger.warning("store_feedback failed (non-blocking): %s", e)
        return None


async def consolidate_contact_memories(contact_email: str) -> dict:
    """
    Consolidate memories for a contact that has more than CONSOLIDATION_THRESHOLD.
    Uses Haiku to summarize all memories into 1-2 consolidated entries.
    """
    all_mems = scroll_by_filter(
        CONTACT_MEMORIES,
        filters={"contact_email": contact_email},
        limit=50,
    )

    if len(all_mems) <= CONSOLIDATION_THRESHOLD:
        return {"status": "skip", "count": len(all_mems), "reason": "below threshold"}

    all_mems.sort(key=lambda r: r.get("stored_at", ""))

    observations_text = "\n".join(
        f"- [{m.get('stored_at', '?')[:10]}] {m.get('observation', '')} "
        f"(strategia: {m.get('strategy_used', 'N/A')}, esito: {m.get('outcome', 'N/A')})"
        for m in all_mems
    )

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    consolidation_prompt = f"""Sei un sistema di consolidamento memoria. Devi comprimere queste {len(all_mems)} osservazioni su un lead in 1-2 riassunti.

OSSERVAZIONI (dalla più vecchia alla più recente):
{observations_text}

Produci un JSON con 1-2 memorie consolidate. Ogni memoria deve catturare le informazioni essenziali.
Formato: {{"memories": [{{"observation": "riassunto...", "strategy_used": "strategie usate", "outcome": "esito generale"}}]}}"""

    try:
        resp = await client.messages.create(
            model=settings.model_router,
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": consolidation_prompt}],
        )
        text = resp.content[0].text.strip()
        parsed = json.loads(text[text.index("{"):text.rindex("}") + 1])
        new_memories = parsed.get("memories", [])

        if not new_memories:
            return {"status": "error", "reason": "no memories produced"}

        old_ids = [m["id"] for m in all_mems]
        from qdrant_client.models import PointIdsList
        qdrant = get_qdrant_client()
        qdrant.delete(
            collection_name=_collection_name(CONTACT_MEMORIES),
            points_selector=PointIdsList(points=old_ids),
        )

        from datetime import datetime, timezone
        for mem in new_memories:
            vector = embed_single(f"{contact_email} {mem['observation']}")
            upsert_point(CONTACT_MEMORIES, vector, {
                "contact_email": contact_email,
                "observation": mem["observation"],
                "strategy_used": mem.get("strategy_used", ""),
                "outcome": mem.get("outcome", ""),
                "conversation_id": "consolidated",
                "task_type": "consolidation",
                "stored_at": datetime.now(timezone.utc).isoformat(),
            })

        logger.info(
            "Consolidated %d memories into %d for %s",
            len(old_ids), len(new_memories), contact_email,
        )
        return {
            "status": "consolidated",
            "original_count": len(old_ids),
            "new_count": len(new_memories),
        }
    except Exception as e:
        logger.error("Memory consolidation failed for %s: %s", contact_email, e)
        return {"status": "error", "reason": str(e)}


async def consolidate_all_contacts() -> dict:
    """
    Batch consolidation: find all contacts with many memories and consolidate them.
    Intended to be called by a periodic job (daily).
    """
    qdrant = get_qdrant_client()
    all_points, _ = qdrant.scroll(
        collection_name=_collection_name(CONTACT_MEMORIES),
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )

    email_counts: dict[str, int] = {}
    for p in all_points:
        email = p.payload.get("contact_email", "")
        if email:
            email_counts[email] = email_counts.get(email, 0) + 1

    candidates = [e for e, c in email_counts.items() if c > CONSOLIDATION_THRESHOLD]
    results = []
    for email in candidates:
        result = await consolidate_contact_memories(email)
        results.append({"email": email, **result})

    logger.info("Batch consolidation complete: %d contacts processed", len(results))
    return {"processed": len(results), "results": results}
