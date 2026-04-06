"""
Memory Recall node — retrieves episodic examples and contact memories from Qdrant.

Queries two collections:
  1. episodes: similar past interactions (for few-shot learning)
  2. contact_memories: agent's own observations about this specific lead
"""

import logging

from app.graph.state import AgentState
from app.memory.manager import recall_all

logger = logging.getLogger("agent-service.nodes.memory")


def _build_recall_context(state: AgentState) -> dict:
    """Build a context dict for episodic similarity search from current state."""
    request = state["request"]
    research = state.get("research", {})
    contact = research.get("contact", {})

    context = {
        "lead_profile": {
            "category": contact.get("category"),
            "city": contact.get("city"),
            "source": contact.get("source"),
            "status": contact.get("status"),
            "rating": contact.get("rating"),
            "reviews": contact.get("reviews"),
        },
        "task_type": getattr(request, "task_type", ""),
        "stage": getattr(request, "stage", "initial_reply"),
        "objections": list(getattr(request, "existing_objections", []) or []),
    }

    lead_message = getattr(request, "lead_message", "")
    task_ctx = getattr(request, "task_context", {}) or {}
    if lead_message:
        context["situation"] = lead_message[:300]
    elif task_ctx.get("reason"):
        context["situation"] = f"{context['task_type']}: {task_ctx['reason']}"

    crm_context = research.get("crm_context")
    if crm_context:
        context["situation"] = (context.get("situation", "") + " " + crm_context[:200]).strip()

    return context


async def memory_recall_node(state: AgentState) -> dict:
    request = state["request"]
    contact_email = request.contact.email

    context = _build_recall_context(state)

    try:
        memories = await recall_all(
            contact_email=contact_email,
            context=context,
            episodic_top_k=3,
            contact_limit=10,
        )
    except Exception as e:
        logger.warning("Memory recall failed (continuing without memory): %s", e)
        return {"episodic_examples": [], "contact_memories": []}

    return {
        "episodic_examples": memories["episodic_examples"],
        "contact_memories": memories["contact_memories"],
    }
