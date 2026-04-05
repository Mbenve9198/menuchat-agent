"""
Memory Manager — orchestrates episodic and semantic memory.
Phase 3 implementation. Stub for now.
"""

import logging

logger = logging.getLogger("agent-service.memory")


async def store_episode(conversation_id: str, strategy: dict, draft: str, outcome: str):
    """Store a winning episode for future few-shot retrieval. TODO Phase 3."""
    logger.debug("store_episode stub: conv=%s outcome=%s", conversation_id, outcome)


async def recall_episodes(context: dict, top_k: int = 3) -> list[dict]:
    """Retrieve top-k similar winning episodes. TODO Phase 3."""
    return []
