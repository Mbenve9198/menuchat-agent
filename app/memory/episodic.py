"""
Episodic memory — stores and retrieves sales interaction episodes.

Each episode captures:
  - The situation (lead profile, objections, context)
  - The strategy chosen by the strategist
  - The draft produced
  - The outcome (approved/modified/discarded) and human corrections

Used to provide few-shot examples to the strategist for similar situations.
"""

import logging
from datetime import datetime, timezone

from app.memory.embeddings import embed_single
from app.memory.qdrant_store import EPISODES, search_similar, upsert_point

logger = logging.getLogger("agent-service.memory.episodic")


def _build_episode_text(episode: dict) -> str:
    """Build a text representation for embedding from episode data."""
    parts = []

    lead = episode.get("lead_profile", {})
    if lead.get("category"):
        parts.append(f"Tipo: {lead['category']}")
    if lead.get("city"):
        parts.append(f"Città: {lead['city']}")
    if lead.get("source"):
        parts.append(f"Fonte: {lead['source']}")
    if lead.get("status"):
        parts.append(f"Stato: {lead['status']}")

    if episode.get("situation"):
        parts.append(f"Situazione: {episode['situation']}")
    if episode.get("objections"):
        parts.append(f"Obiezioni: {', '.join(episode['objections'])}")
    if episode.get("task_type"):
        parts.append(f"Tipo azione: {episode['task_type']}")
    if episode.get("stage"):
        parts.append(f"Fase: {episode['stage']}")
    if episode.get("strategy"):
        parts.append(f"Strategia: {episode['strategy']}")

    return " | ".join(parts) if parts else "unknown context"


async def store_episode(episode: dict) -> str:
    """
    Store a feedback episode in Qdrant for future retrieval.

    episode should contain:
      - lead_profile: {category, city, source, status, rating, reviews}
      - situation: free text describing the context
      - objections: list of objection strings
      - task_type: e.g. 'reactivation', 'follow_up_no_reply'
      - stage: conversation stage
      - strategy: strategy description from strategist
      - strategy_reasoning: strategist's thinking
      - draft: the agent's draft text
      - outcome: 'approved' | 'modified' | 'discarded'
      - human_edits: {final_sent, discard_reason, discard_notes, modifications}
      - conversation_id: for traceability
      - contact_email: for traceability
    """
    text = _build_episode_text(episode)
    vector = embed_single(text)

    payload = {
        "lead_profile": episode.get("lead_profile", {}),
        "situation": episode.get("situation", ""),
        "objections": episode.get("objections", []),
        "task_type": episode.get("task_type", ""),
        "stage": episode.get("stage", ""),
        "strategy": episode.get("strategy", ""),
        "strategy_reasoning": episode.get("strategy_reasoning", "")[:1000],
        "draft": episode.get("draft", "")[:2000],
        "outcome": episode.get("outcome", "unknown"),
        "human_edits": episode.get("human_edits", {}),
        "conversation_id": episode.get("conversation_id", ""),
        "contact_email": episode.get("contact_email", ""),
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }

    point_id = upsert_point(EPISODES, vector, payload)
    logger.info(
        "Stored episode: outcome=%s strategy=%s id=%s",
        payload["outcome"], payload["strategy"][:80], point_id,
    )
    return point_id


async def recall_similar_episodes(
    context: dict,
    top_k: int = 3,
    score_threshold: float = 0.35,
) -> list[dict]:
    """
    Find the most similar past episodes to the current situation.

    context should mirror episode structure (lead_profile, situation, objections, etc).
    Returns list of episodes sorted by similarity, each with a 'score' field.
    """
    text = _build_episode_text(context)
    vector = embed_single(text)

    results = search_similar(
        EPISODES,
        query_vector=vector,
        limit=top_k,
        score_threshold=score_threshold,
    )

    logger.info(
        "Recalled %d episodes (threshold=%.2f, query=%s...)",
        len(results), score_threshold, text[:80],
    )
    return results
