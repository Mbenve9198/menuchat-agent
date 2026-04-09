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


CRITIC_PROMPT = """Sei un fact-checker per strategie di vendita. Il tuo ruolo NON è giudicare la creatività o l'approccio dello strategist — lui è più intelligente di te su quello. Il tuo ruolo è SOLO verificare errori oggettivi.

BOCCIA SOLO SE trovi uno di questi problemi CONCRETI:
1. ALLUCINAZIONE DATI: La strategia cita nomi di clienti, numeri, statistiche o fatti che NON esistono nei dati di ricerca forniti. Se dice "il ristorante X ha Y recensioni" e quel dato non è nei research data → FAIL.
2. CONTRADDIZIONE LOGICA: La strategia si contraddice internamente (es: dice "non parlare del prezzo" ma poi nel message_plan dice "menziona il costo").
3. VIOLAZIONE ESPLICITA: La strategia propone un'azione che viola una regola nei do_not che lo strategist stesso ha definito.

NON BOCCIARE per:
- Scelte di tono o approccio — lo strategist ha più contesto di te
- La CTA che ritieni "troppo presto" o "troppo tardi" — lo strategist ragiona con thinking esteso
- Strategie creative o non convenzionali — sono intenzionali
- Lunghezza o struttura del messaggio pianificato

In caso di dubbio, APPROVA. Meglio un messaggio imperfetto che un loop infinito di riscritture.

Rispondi SOLO con JSON:
{"approved": true, "feedback": ""}
oppure
{"approved": false, "feedback": "ERRORE FATTUALE: [dato inventato] non esiste nei research data. Correggere citando solo dati verificati."}"""


async def strategy_critic_node(state: AgentState) -> dict:
    strategy = state.get("strategy", {})
    research = state.get("research", {})
    attempts = state.get("strategy_attempts", 0)

    if attempts >= 2:
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
