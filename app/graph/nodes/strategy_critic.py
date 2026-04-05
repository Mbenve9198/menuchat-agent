"""
Strategy Critic node — validates the strategist's plan BEFORE text generation.
Uses Sonnet for fast, focused evaluation.
"""

import json
import logging

import anthropic

from app.config import get_settings
from app.graph.state import AgentState

logger = logging.getLogger("agent-service.nodes.critic")

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


CRITIC_PROMPT = """Sei un quality critic per strategie di vendita. Valuta il piano dello strategist.

CRITERI DI VALIDAZIONE:
1. COERENZA: La strategia è coerente con il messaggio del lead? (es: se il lead chiede il prezzo, la strategia deve affrontare il prezzo)
2. DATI: I dati citati in data_to_include esistono nel RESEARCH DATA fornito? Se cita un cliente/nome/numero che non è nei dati → FAIL
3. CTA: La call-to-action è appropriata per la fase? (non proporre chiamata al primo contatto outbound se il lead non ha mostrato interesse)
4. DIVIETI: La strategia rispetta i do_not? (es: non citare prezzo al primo contatto rank checker)
5. OBIETTIVO: La strategia converge verso l'obiettivo (fissare chiamata di 5 minuti)?
6. TONE: Il tono è appropriato per il contesto? (es: non essere aggressivo con un lead che dice "non mi interessa")

Rispondi SOLO con JSON:
{"approved": true, "feedback": ""}
oppure
{"approved": false, "feedback": "Problema specifico: ... Cosa correggere: ..."}"""


async def strategy_critic_node(state: AgentState) -> dict:
    strategy = state.get("strategy", {})
    research = state.get("research", {})
    attempts = state.get("strategy_attempts", 0)

    if attempts >= 3:
        logger.warning("Strategy critic: max attempts reached, forcing approval")
        return {"strategy_approved": True, "strategy_feedback": None}

    research_summary = research.get("available_data_summary", "N/A")

    user_content = (
        f"PIANO STRATEGICO:\n{json.dumps(strategy, ensure_ascii=False, indent=2)}\n\n"
        f"DATI DI RICERCA DISPONIBILI:\n{research_summary}"
    )

    settings = get_settings()
    client = _get_client()

    try:
        resp = await client.messages.create(
            model=settings.model_critic,
            max_tokens=500,
            temperature=0,
            system=CRITIC_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        text = resp.content[0].text.strip()
        parsed = json.loads(text[text.index("{"):text.rindex("}") + 1])

        approved = parsed.get("approved", True)
        feedback = parsed.get("feedback", "")

        logger.info("Strategy critic: approved=%s feedback=%s", approved, feedback[:200] if feedback else "none")

        return {
            "strategy_approved": approved,
            "strategy_feedback": feedback if not approved else None,
            "total_input_tokens": state.get("total_input_tokens", 0) + (resp.usage.input_tokens or 0),
            "total_output_tokens": state.get("total_output_tokens", 0) + (resp.usage.output_tokens or 0),
        }
    except Exception as e:
        logger.warning("Strategy critic failed, auto-approving: %s", e)
        return {"strategy_approved": True, "strategy_feedback": None}
