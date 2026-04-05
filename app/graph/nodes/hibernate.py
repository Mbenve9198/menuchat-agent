"""
Hibernate node — Durable Execution suspension point.
Saves the graph state to PostgreSQL checkpoint and emits a hibernate_workflow tool intent.
When the task fires months later, the graph resumes from this exact point.
"""

import logging

from app.graph.state import AgentState

logger = logging.getLogger("agent-service.nodes.hibernate")


async def hibernate_node(state: AgentState) -> dict:
    strategy = state.get("strategy", {})
    hibernate_config = strategy.get("hibernate", {})

    if not hibernate_config:
        logger.warning("Hibernate node called but no hibernate config in strategy")
        return {}

    thread_id = state.get("thread_id", "unknown")

    tool_intents = list(state.get("tool_intents", []))
    tool_intents.append({
        "tool": "hibernate_workflow",
        "params": {
            "thread_id": thread_id,
            "wake_at": hibernate_config.get("wake_at"),
            "task_type": hibernate_config.get("task_type", "seasonal_reactivation"),
            "context": {"reason": hibernate_config.get("reason", "Scheduled reactivation")},
            "priority": "high",
        },
    })

    logger.info(
        "Hibernate: thread=%s wake_at=%s type=%s",
        thread_id, hibernate_config.get("wake_at"), hibernate_config.get("task_type"),
    )

    return {"tool_intents": tool_intents}
