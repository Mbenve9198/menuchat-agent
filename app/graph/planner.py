"""
Agent Planner — autonomous event-driven decision-maker.

Receives events from the CRM (new lead, reply received, timer expired, status change)
and returns a list of proposed actions. The CRM's guardrail layer validates and executes them.

This replaces the CRM-side task generation logic, putting the AI in charge of WHAT to do
while the CRM retains control over WHEN and IF to execute (guardrails).
"""

import json
import logging
from datetime import datetime, timezone

import anthropic

from app.config import get_settings
from app.memory.contact_memory import recall_contact_history

logger = logging.getLogger("agent-service.planner")

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


PLANNER_SYSTEM = """Sei il planner autonomo dell'agente di vendita MenuChat.

Ricevi EVENTI dal CRM e decidi QUALI AZIONI intraprendere.

EVENTI POSSIBILI:
- new_lead: nuovo lead acquisito (rank checker, inbound, etc.)
- reply_received: il lead ha risposto a un nostro messaggio
- no_reply_timeout: il lead non ha risposto entro X giorni
- status_changed: cambio stato del contatto nel CRM
- timer_expired: un timer programmato è scaduto
- manual_trigger: attivazione manuale dall'operatore

AZIONI CHE PUOI PROPORRE:
- send_outreach: primo contatto con il lead
- send_follow_up: follow-up dopo nessuna risposta
- send_break_up: ultimo tentativo prima di chiudere
- send_reactivation: riattivazione di un lead dormiente
- schedule_task: programma un'azione futura
- escalate_human: passa al team umano
- mark_terminal: segna il contatto come terminale (non contattare più)
- do_nothing: nessuna azione necessaria

REGOLE:
1. Non contattare lead in stato terminale
2. Max 3 tentativi senza risposta prima di break_up
3. Rispetta il timing: non inviare di notte o weekend
4. Se il lead ha risposto, la priorità è la risposta (gestita dal flusso reattivo)
5. Se non hai abbastanza contesto, proponi do_nothing con motivo
6. Considera lo storico delle interazioni per decidere

OUTPUT: JSON valido con lista di azioni proposte:
{
  "reasoning": "Il tuo ragionamento",
  "actions": [
    {
      "action": "send_follow_up",
      "priority": "high" | "medium" | "low",
      "task_type": "follow_up_no_reply",
      "delay_hours": 0,
      "context": {"reason": "motivo specifico"}
    }
  ],
  "confidence": 0.0-1.0
}"""


async def plan_actions(event: dict) -> dict:
    """
    Given a CRM event, plan the agent's next actions.

    Args:
        event: {
            "type": "new_lead" | "reply_received" | "no_reply_timeout" | ...,
            "contact": { email, name, status, ... },
            "conversation": { stage, messages_count, last_message_at, ... },
            "context": { ... additional context ... }
        }

    Returns:
        {
            "actions": [...],
            "reasoning": "...",
            "confidence": 0.0-1.0,
        }
    """
    contact_email = event.get("contact", {}).get("email", "")
    contact_memories = []
    if contact_email:
        try:
            contact_memories = await recall_contact_history(contact_email, limit=5)
        except Exception as e:
            logger.warning("Planner: memory recall failed: %s", e)

    memory_context = ""
    if contact_memories:
        memory_context = "\n\nMEMORIA AGENTE SU QUESTO LEAD:\n" + "\n".join(
            f"- [{m.get('stored_at', '')[:10]}] {m.get('observation', '')} → {m.get('outcome', '')}"
            for m in contact_memories[:5]
        )

    user_input = f"""EVENTO: {event.get('type', 'unknown')}
TIMESTAMP: {datetime.now(timezone.utc).isoformat()}

CONTATTO:
{json.dumps(event.get('contact', {}), ensure_ascii=False, indent=2)}

CONVERSAZIONE:
{json.dumps(event.get('conversation', {}), ensure_ascii=False, indent=2)}

CONTESTO AGGIUNTIVO:
{json.dumps(event.get('context', {}), ensure_ascii=False, indent=2)}
{memory_context}

Che azioni proponi?"""

    settings = get_settings()
    client = _get_client()

    try:
        thinking_text = ""
        output_text = ""

        async with client.messages.stream(
            model=settings.model_planner,
            max_tokens=settings.planner_max_tokens,
            temperature=1,
            thinking={"type": "enabled", "budget_tokens": settings.planner_thinking_budget},
            system=PLANNER_SYSTEM,
            messages=[{"role": "user", "content": user_input}],
        ) as stream:
            resp = await stream.get_final_message()

        for block in resp.content:
            if block.type == "thinking":
                thinking_text += block.thinking
            elif block.type == "text":
                output_text += block.text

        if thinking_text:
            logger.info("Planner thinking: %s...", thinking_text[:500])

        parsed = json.loads(output_text[output_text.index("{"):output_text.rindex("}") + 1])

        actions = parsed.get("actions", [])
        reasoning = parsed.get("reasoning", "")
        confidence = parsed.get("confidence", 0.5)

        logger.info(
            "Planner: %d actions proposed for %s (confidence=%.2f) — %s",
            len(actions), contact_email, confidence, reasoning[:200],
        )

        return {
            "actions": actions,
            "reasoning": reasoning,
            "confidence": confidence,
            "tokens_used": (resp.usage.input_tokens or 0) + (resp.usage.output_tokens or 0),
        }
    except Exception as e:
        logger.error("Planner failed: %s", e)
        return {
            "actions": [{"action": "do_nothing", "priority": "low", "context": {"reason": f"Planner error: {e}"}}],
            "reasoning": f"Error: {e}",
            "confidence": 0.0,
        }
