"""
Sales Manager Agent — Opus with extended thinking.

Periodic supervisory agent that analyzes team performance,
produces strategic directives, briefings, and intelligent alerts.
"""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

from app.config import get_settings

logger = logging.getLogger("agent-service.sales_manager")

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


SALES_MANAGER_SYSTEM = """Sei il Sales Manager del team vendita MenuChat.
Il tuo team e' composto da agenti AI che contattano ristoratori italiani per proporre un sistema di raccolta recensioni via QR code + WhatsApp.

Ricevi un report periodico con tutti i dati delle ultime ore di lavoro del team.
Il tuo compito: analizzare tutto, capire cosa sta funzionando e cosa no, e produrre direttive strategiche per il team.

Non hai regole fisse. Hai DATI e INTELLIGENZA. Ragiona liberamente.

Pensa come un sales manager esperto che ha a cuore i risultati ma anche la qualita' del lavoro:
- Quali lead meritano piu' attenzione? Quali sono causa persa?
- Quale approccio sta convertendo e quale sta fallendo?
- C'e' qualcosa di anomalo che richiede attenzione immediata?
- Il team sta sprecando risorse (tempo, soldi API) su lead che non convertiranno?
- I feedback umani indicano un pattern? (troppo aggressivo? troppo timido? errori fattuali?)
- C'e' un'opportunita' che il team sta perdendo?
- Il timing dei messaggi e' giusto? Stiamo contattando nei momenti sbagliati?
- Il costo per lead e' sostenibile? Come possiamo ottimizzare?

Le tue direttive arriveranno direttamente allo Strategist e al Planner del team.
Lo Strategist decide la strategia per ogni singolo lead.
Il Planner decide quali lead contattare e quando.
Le tue direttive devono essere UTILI e CONCRETE — non generiche.

OUTPUT: JSON valido con questa struttura:
{
  "directives": [
    {
      "scope": "strategist" | "planner" | "all",
      "directive": "Testo libero della direttiva — chiaro, specifico, azionabile",
      "reason": "Perche' questa direttiva, basata su quali dati",
      "priority": "high" | "medium" | "low",
      "expires_hours": 24
    }
  ],
  "briefing": {
    "headline": "Una riga che cattura lo stato attuale",
    "summary": "Riassunto in 3-5 frasi dello stato del team",
    "highlights": ["cosa sta andando bene"],
    "concerns": ["cosa preoccupa"],
    "next_actions": ["suggerimenti concreti per Marco"]
  },
  "alerts": [
    {
      "severity": "critical" | "warning" | "info",
      "message": "Descrizione dell'alert",
      "affected_contacts": ["email1"],
      "suggested_action": "Cosa fare"
    }
  ],
  "performance": {
    "conversion_rate": 0.15,
    "approval_rate": 0.80,
    "avg_cost_per_lead_usd": 0.35,
    "top_strategy": "nome strategia migliore",
    "worst_strategy": "nome strategia peggiore",
    "by_source": {
      "rank_checker": {"contacted": 0, "responded": 0, "converted": 0},
      "reactivation": {"contacted": 0, "responded": 0, "converted": 0},
      "smartlead": {"contacted": 0, "responded": 0, "converted": 0}
    }
  }
}"""


async def analyze_performance(report_data: dict) -> dict:
    """
    Analyze team performance and produce directives, briefing, and alerts.

    Args:
        report_data: Aggregated data from the CRM including metrics,
                     logs, feedback, conversations, outcomes, and tasks.

    Returns:
        Structured output with directives, briefing, alerts, performance.
    """
    now_rome = datetime.now(tz=ZoneInfo("Europe/Rome"))

    user_input = f"""TIMESTAMP: {now_rome.strftime('%A %d %B %Y, ore %H:%M')} (Roma)

REPORT DATI TEAM (ultime ore):

METRICHE COSTI E VOLUMI:
{json.dumps(report_data.get('metrics', {}), ensure_ascii=False, indent=2)}

CONVERSAZIONI ATTIVE:
{json.dumps(report_data.get('conversations', {}), ensure_ascii=False, indent=2)}

OUTCOME RECENTI:
{json.dumps(report_data.get('outcomes', {}), ensure_ascii=False, indent=2)}

FEEDBACK UMANI (approvazioni/modifiche/scarti):
{json.dumps(report_data.get('feedback', {}), ensure_ascii=False, indent=2)}

TASK SYSTEM:
{json.dumps(report_data.get('tasks', {}), ensure_ascii=False, indent=2)}

ERRORI E WARNING:
{json.dumps(report_data.get('errors', []), ensure_ascii=False, indent=2)}

DETTAGLI CONVERSAZIONI SIGNIFICATIVE:
{json.dumps(report_data.get('significant_conversations', []), ensure_ascii=False, indent=2)}

Analizza tutto e produci il tuo report."""

    settings = get_settings()
    client = _get_client()

    try:
        thinking_text = ""
        output_text = ""

        async with client.messages.stream(
            model=settings.model_strategist,
            max_tokens=16000,
            temperature=1,
            thinking={"type": "enabled", "budget_tokens": 16000},
            system=SALES_MANAGER_SYSTEM,
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
            logger.info("Sales Manager thinking: %s...", thinking_text[:800])

        parsed = json.loads(output_text[output_text.index("{"):output_text.rindex("}") + 1])

        logger.info(
            "Sales Manager: %d directives, %d alerts, tokens=%d+%d",
            len(parsed.get("directives", [])),
            len(parsed.get("alerts", [])),
            input_tokens, output_tokens,
        )

        return {
            "directives": parsed.get("directives", []),
            "briefing": parsed.get("briefing", {}),
            "alerts": parsed.get("alerts", []),
            "performance": parsed.get("performance", {}),
            "thinking": thinking_text[:2000],
            "tokens_used": input_tokens + output_tokens,
            "estimated_cost_usd": round((input_tokens * 15 + output_tokens * 75) / 1_000_000, 4),
        }
    except Exception as e:
        logger.error("Sales Manager failed: %s", e)
        return {
            "directives": [],
            "briefing": {"headline": "Errore analisi", "summary": str(e)},
            "alerts": [{"severity": "warning", "message": f"Sales Manager error: {e}"}],
            "performance": {},
            "error": str(e),
        }
