"""
Build Response node — assembles the final AgentResponse from graph state.
Also stores per-contact memory observations extracted from the strategist's reasoning.
"""

import logging

from app.api.models import AgentResponse, ToolIntent, Insights, StrategyOutput
from app.graph.state import AgentState
from app.memory.manager import store_run_memory

logger = logging.getLogger("agent-service.nodes.response")

COST_PER_INPUT_TOKEN = {
    "opus": 5.0 / 1_000_000,
    "sonnet": 3.0 / 1_000_000,
    "haiku": 1.0 / 1_000_000,
}
COST_PER_OUTPUT_TOKEN = {
    "opus": 25.0 / 1_000_000,
    "sonnet": 15.0 / 1_000_000,
    "haiku": 5.0 / 1_000_000,
}

TERMINAL_KEYWORDS = [
    "business_closed", "chiuso", "chiusura",
    "not_interested_final", "rifiuto definitivo",
    "wrong_contact", "contatto errato",
    "deceased", "deceduto",
]


def _detect_terminal_state(strategy: dict) -> str | None:
    """Check if the strategy indicates a terminal situation (business closed, etc.)."""
    approach = (strategy.get("strategy") or strategy.get("approach") or "").lower()
    reasoning = (strategy.get("reasoning") or "").lower()
    combined = f"{approach} {reasoning}"

    if any(kw in combined for kw in ["business_closed", "chiuso definitivamente", "non è più aperto",
                                      "chiusura definitiva", "ristorante chiuso", "attività chiusa"]):
        return "business_closed"
    if any(kw in combined for kw in ["not_interested_final", "rifiuto definitivo", "non contattare più"]):
        return "not_interested_final"
    if any(kw in combined for kw in ["wrong_contact", "contatto errato", "numero sbagliato"]):
        return "wrong_contact"
    return None


async def build_response_node(state: AgentState) -> dict:
    strategy = state.get("strategy") or {}
    draft = state.get("draft")
    review = state.get("review_result") or {}
    tool_intents = list(state.get("tool_intents", []))

    terminal_status = _detect_terminal_state(strategy)

    # Determine action
    if terminal_status:
        action = "terminal"
        tool_intents.append({
            "tool": "mark_contact_terminal",
            "params": {
                "terminal_reason": terminal_status,
                "cancel_pending_tasks": True,
            },
        })
        logger.info("Terminal state detected: %s", terminal_status)
    elif strategy.get("hibernate"):
        action = "hibernated"
    elif strategy.get("escalate_human"):
        action = "escalate_human"
    elif draft and review.get("pass", False):
        action = "draft_ready"
    elif draft and not review.get("pass", False):
        action = "awaiting_human"
    else:
        action = "escalate_human"

    channel = strategy.get("channel", "email")

    if state.get("request_type") == "reactive":
        request = state.get("request")
        if request:
            msgs = getattr(request, "messages", []) or []
            for m in reversed(msgs):
                role = m.role if hasattr(m, "role") else m.get("role", "")
                if role == "lead":
                    inbound_ch = m.channel if hasattr(m, "channel") else m.get("channel", "email")
                    if inbound_ch != "email":
                        channel = inbound_ch
                    break

    # Accumulate future actions as schedule_task intents
    for fa in strategy.get("future_actions", []):
        fa_type = fa.get("type", "schedule_task")
        if fa_type == "hibernate_workflow":
            continue  # handled by hibernate node
        delay = fa.get("delay_days", 3)
        from datetime import datetime, timedelta, timezone
        wake = datetime.now(timezone.utc) + timedelta(days=delay)
        tool_intents.append({
            "tool": "schedule_task",
            "params": {
                "task_type": fa.get("task_type", "follow_up_no_reply"),
                "scheduled_at": wake.isoformat(),
                "context": {"reason": fa.get("reason", ""), "attempt": fa.get("attempt", 1)},
                "priority": fa.get("priority", "medium"),
            },
        })

    # Build strategy output for logging
    strategy_out = StrategyOutput(
        approach=strategy.get("strategy") or strategy.get("approach"),
        main_angle=strategy.get("reasoning", "")[:500],
        tone=strategy.get("tone_description") or strategy.get("tone"),
        reasoning=strategy.get("thinking", "")[:2000],
        raw=strategy,
    )

    # Estimate cost (rough, uses Opus as primary)
    input_t = state.get("total_input_tokens", 0)
    output_t = state.get("total_output_tokens", 0)
    cost = input_t * COST_PER_INPUT_TOKEN["opus"] + output_t * COST_PER_OUTPUT_TOKEN["opus"]

    research = state.get("research") or {}
    research_summary = research.get("available_data_summary", "")

    email_subject = strategy.get("email_subject")
    whatsapp_draft = state.get("whatsapp_draft")

    response = AgentResponse(
        action=action,
        draft=draft,
        whatsapp_draft=whatsapp_draft,
        email_subject=email_subject,
        channel=channel,
        strategy=strategy_out,
        tool_intents=[ToolIntent(**ti) for ti in tool_intents],
        new_stage=_infer_stage(strategy, action),
        extracted_insights=Insights(),
        research_summary=research_summary[:3000] if research_summary else None,
        thinking=strategy.get("thinking", "")[:2000],
        model_used="opus-4.6",
        total_tokens=input_t + output_t,
        estimated_cost_usd=round(cost, 4),
    )

    await _store_contact_observation(state, strategy, action)

    return {"response": response}


async def _store_contact_observation(state: AgentState, strategy: dict, action: str):
    """Extract and store the agent's observation about this contact."""
    try:
        request = state["request"]
        contact_email = request.contact.email
        reasoning = strategy.get("reasoning", "")
        approach = strategy.get("strategy") or strategy.get("approach", "")

        if not reasoning and not approach:
            return

        observation_parts = []
        if approach:
            observation_parts.append(f"Strategia: {approach}")
        if reasoning:
            observation_parts.append(f"Analisi: {reasoning[:500]}")

        tone = strategy.get("tone_description") or strategy.get("tone", "")
        if tone:
            observation_parts.append(f"Tono scelto: {tone}")

        do_not = strategy.get("do_not", [])
        if do_not:
            observation_parts.append(f"Da evitare: {', '.join(do_not[:3])}")

        observation = " | ".join(observation_parts)

        conversation_id = getattr(request, "conversation_id", "") or ""
        task_type = getattr(request, "task_type", "") or getattr(request, "stage", "")

        await store_run_memory(
            contact_email=contact_email,
            observation=observation,
            strategy_used=approach,
            outcome=action,
            conversation_id=conversation_id,
            task_type=task_type,
        )
    except Exception as e:
        logger.warning("Failed to store contact observation (non-blocking): %s", e)


def _infer_stage(strategy: dict, action: str) -> str | None:
    if action == "terminal":
        return "terminal"
    if action == "hibernated":
        return "dormant"

    proposed = strategy.get("new_stage")
    if proposed:
        return proposed

    approach = strategy.get("approach", "")
    if approach in ("escalate_human",):
        return "handoff"
    if strategy.get("future_actions"):
        for fa in strategy["future_actions"]:
            if fa.get("task_type") == "human_task":
                return "handoff"
    return None
