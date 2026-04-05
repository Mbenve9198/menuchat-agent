"""
Memory Recall node — retrieves relevant episodic examples from Mem0/Qdrant.
Phase 3 implementation. For now, returns empty list (no-op).
"""

import logging

from app.graph.state import AgentState

logger = logging.getLogger("agent-service.nodes.memory")


async def memory_recall_node(state: AgentState) -> dict:
    """
    TODO (Phase 3): Query Mem0 for top-3 winning episodes similar to current context.
    For now, returns empty episodic examples.
    """
    return {"episodic_examples": []}
