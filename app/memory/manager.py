"""
Memory Manager — orchestrates episodic and contact memory.

Provides high-level functions used by graph nodes:
  - recall_all(): fetch both episodic + contact memories for a run
  - store_run_memory(): save contact observation after a run completes
  - store_feedback(): save a human feedback episode
"""

import logging

from app.memory.episodic import recall_similar_episodes, store_episode
from app.memory.contact_memory import recall_contact_history, store_observation

logger = logging.getLogger("agent-service.memory.manager")


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
