"""
Strategist node — Opus 4.6 with 32k extended thinking.
The strategic brain of the agent.
"""

import json
import logging

import anthropic

from app.config import get_settings
from app.graph.state import AgentState
from app.prompts.strategist import build_strategist_system_prompt, build_strategist_user_input

logger = logging.getLogger("agent-service.nodes.strategist")

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


def _build_conversation_context(request) -> str:
    parts = []
    objections = getattr(request, "existing_objections", []) or []
    if objections:
        parts.append(f"OBIEZIONI GIÀ EMERSE: {', '.join(objections)}")
    pain_points = getattr(request, "existing_pain_points", []) or []
    if pain_points:
        parts.append(f"PAIN POINTS RILEVATI: {', '.join(pain_points)}")

    stage = getattr(request, "stage", "initial_reply")
    parts.append(f"FASE: {stage}")

    messages = getattr(request, "messages", []) or []
    parts.append(f"MESSAGGI SCAMBIATI: {len(messages)}")

    is_first = getattr(request, "is_first_contact", False)
    if is_first:
        parts.append("TIPO: PRIMO CONTATTO (l'agente contatta per primo, il lead non ha scritto)")

    lead_source = getattr(request, "lead_source", "smartlead_outbound")
    parts.append(f"FONTE LEAD: {lead_source}")

    days = getattr(request, "days_since_last_contact", None)
    if days:
        parts.append(f"GIORNI DALL'ULTIMO CONTATTO: {days}")

    task_type = getattr(request, "task_type", None)
    if task_type:
        parts.append(f"TIPO TASK: {task_type}")

    summary = getattr(request, "conversation_summary", None)
    if summary:
        parts.append(f"RIASSUNTO CONVERSAZIONE: {summary}")

    if messages and len(messages) > 0:
        recent = messages[-6:] if len(messages) > 6 else messages
        parts.append("\nULTIMI MESSAGGI:")
        for m in recent:
            role = m.role if hasattr(m, "role") else m.get("role", "?")
            content = m.content if hasattr(m, "content") else m.get("content", "")
            parts.append(f"[{role.upper()}]: {content[:300]}")

    return "\n".join(parts)


async def strategist_node(state: AgentState) -> dict:
    request = state["request"]
    research = state.get("research", {})
    episodic = state.get("episodic_examples", [])
    feedback = state.get("strategy_feedback")
    attempts = state.get("strategy_attempts", 0)

    lead_message = getattr(request, "lead_message", "") or ""
    if not lead_message:
        task_ctx = getattr(request, "task_context", {}) or {}
        lead_message = f"[AZIONE PROATTIVA: {getattr(request, 'task_type', 'unknown')}] {task_ctx.get('reason', '')}"

    conversation_context = _build_conversation_context(request)

    system_prompt = build_strategist_system_prompt()
    if feedback:
        system_prompt += f"\n\nATTENZIONE — IL CRITIC HA BOCCIATO LA STRATEGIA PRECEDENTE:\n{feedback}\nCorreggi i problemi segnalati."

    contact_mems = state.get("contact_memories", [])
    user_input = build_strategist_user_input(lead_message, research, conversation_context, episodic, contact_mems)

    settings = get_settings()
    client = _get_client()

    thinking_text = ""
    output_text = ""
    input_tokens = 0
    output_tokens = 0

    async with client.messages.stream(
        model=settings.model_strategist,
        max_tokens=settings.strategist_max_tokens,
        temperature=1,
        thinking={"type": "enabled", "budget_tokens": settings.strategist_thinking_budget},
        system=system_prompt,
        messages=[{"role": "user", "content": user_input}],
    ) as stream:
        resp = await stream.get_final_message()

    for block in resp.content:
        if block.type == "thinking":
            thinking_text += block.thinking
        elif block.type == "text":
            output_text += block.text

    input_tokens = resp.usage.input_tokens or 0
    output_tokens = resp.usage.output_tokens or 0

    if thinking_text:
        logger.info("Strategist thinking: %s...", thinking_text[:500])

    try:
        json_match = output_text[output_text.index("{"):output_text.rindex("}") + 1]
        strategy = json.loads(json_match)
        strategy["thinking"] = thinking_text
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Strategist JSON parse error: %s | raw: %s", e, output_text[:500])
        strategy = _default_strategy(research)

    logger.info(
        "Strategist: strategy=%s tone=%s channel=%s tokens=%d+%d",
        (strategy.get("strategy") or strategy.get("approach", ""))[:100],
        (strategy.get("tone_description") or strategy.get("tone", ""))[:50],
        strategy.get("channel"),
        input_tokens, output_tokens,
    )

    return {
        "strategy": strategy,
        "strategy_attempts": attempts + 1,
        "strategy_feedback": None,
        "total_input_tokens": state.get("total_input_tokens", 0) + input_tokens,
        "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
    }


def _default_strategy(research: dict) -> dict:
    return {
        "reasoning": "Fallback strategy — parse error on strategist output",
        "strategy": "Presentati, usa i dati disponibili, proponi la prova gratuita, chiedi il numero per 5 minuti",
        "message_plan": "Saluta con il nome del ristorante. Cita un dato concreto dalla ricerca se disponibile. Proponi la prova gratuita. Chiedi il numero per una chiamata di 5 minuti.",
        "data_to_cite": [],
        "tone_description": "Amichevole e diretto, come un collega",
        "max_words": 100,
        "do_not": [],
        "channel": "email",
        "future_actions": [],
        "escalate_human": False,
        "hibernate": None,
        "thinking": "(fallback strategy)",
    }
