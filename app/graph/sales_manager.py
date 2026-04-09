"""
Sales Manager Agent — Opus with extended thinking + tool use.

Agentic loop that investigates team performance autonomously using
CRM tool endpoints, then produces structured directives and briefing.
"""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
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
Il tuo team include agenti AI che contattano ristoratori italiani per proporre un sistema di raccolta recensioni via QR code + WhatsApp (prezzo: €1,290 setup + €49/mese).

## IL BUSINESS — DEVI CONOSCERLO

Ci sono 3 canali di acquisizione lead, ognuno con dinamiche diverse:

### 1. SMARTLEAD OUTBOUND
Email massive gia' inviate da Smartlead a vecchi clienti/lead. L'agente AI gestisce solo le RISPOSTE:
- Risposta positiva CON numero di telefono → handoff immediato all'umano per chiamata. L'agente NON deve rispondere.
- Risposta positiva SENZA numero → l'agente chiede il numero di telefono.
- Obiezioni → l'agente gestisce le obiezioni.
- Non interessato / unsubscribe → l'agente categorizza come "non interessato", nessuna interazione necessaria.
NOTA: NON e' cold outreach. Sono riattivazioni di contatti che hanno gia' avuto rapporti con noi.

### 2. RANK CHECKER (INBOUND)
Lead che hanno usato il nostro tool gratuito di audit del posizionamento Google Maps.
NON conoscono ancora il prodotto. L'agente li educa e li guida verso la prenotazione di una chiamata.
Alcuni hanno gia' prenotato dal funnel → l'agente non serve per quelli.

### 3. RIATTIVAZIONE
Lead dormienti da entrambi i canali sopra: ghosted, hanno chiesto di essere ricontattati in futuro, inattivi.
L'agente ri-ingaggia con messaggi mirati e contestuali.

## IL TUO RUOLO

Sei un analista strategico. Hai accesso a tool per investigare i dati del CRM.
Parti dalla panoramica generale, poi approfondisci dove vedi anomalie o pattern.

## VINCOLO FONDAMENTALE

NON puoi MAI suggerire di:
- Smettere di contattare un canale (rank checker, smartlead, riattivazione)
- Iniziare o fermare campagne
- Cambiare il target di mercato
- Modificare il pricing

Queste sono decisioni di BUSINESS, non tue. Il tuo ambito e' esclusivamente COME il team lavora:
approccio, tono, timing, uso dei dati del lead, CTA, gestione obiezioni, preparazione pre-chiamata.

## DIRETTIVE

Le tue direttive vanno allo Strategist (decide la strategia per ogni singolo lead) e al Planner (decide chi contattare e quando).

Ogni direttiva DEVE avere un tipo basato sulla solidita' dei dati:
- "observation": fatto puntuale, anche 1 dato. Es: "Il lead X ha dato il numero 6h fa, non e' stato chiamato."
- "pattern": trend osservato su 10+ data points. Es: "L'approccio ROI-first ha 85% approval vs 40% per pricing diretto."
- "recommendation": raccomandazione solida su 50+ data points. Es: "Per rank checker, citare sempre i dati dell'audit."

Se non hai abbastanza dati per un pattern, emetti una observation, non inventare trend.

## OUTPUT FINALE

Dopo aver investigato, produci UN SINGOLO blocco JSON:
{
  "directives": [
    {
      "scope": "strategist | planner | all",
      "type": "observation | pattern | recommendation",
      "directive": "Testo chiaro e azionabile",
      "evidence": "Dati specifici su cui si basa",
      "data_points": 15,
      "confidence": "low | medium | high",
      "expires_hours": 48
    }
  ],
  "briefing": {
    "headline": "Una riga che cattura lo stato attuale",
    "summary": "3-5 frasi sullo stato del team",
    "highlights": ["cosa sta andando bene"],
    "concerns": ["cosa preoccupa"],
    "call_insights": "Pattern emersi dalle chiamate (se disponibili)",
    "next_actions": ["suggerimenti concreti per Marco"]
  },
  "alerts": [
    {
      "severity": "critical | warning | info",
      "message": "Descrizione",
      "affected_contacts": ["email1"],
      "suggested_action": "Cosa fare"
    }
  ],
  "performance": {
    "conversion_rate": 0.0,
    "approval_rate": 0.0,
    "avg_cost_per_lead_usd": 0.0,
    "by_source": {
      "rank_checker": {"contacted": 0, "responded": 0, "converted": 0},
      "reactivation": {"contacted": 0, "responded": 0, "converted": 0},
      "smartlead": {"contacted": 0, "responded": 0, "converted": 0}
    }
  }
}"""


TOOLS = [
    {
        "name": "get_overview",
        "description": (
            "Panoramica generale del team: conversazioni per status/source/stage, "
            "tasso approvazione, costi ultimi 24h, errori, task, chiamate completate. "
            "Inizia SEMPRE da qui."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_conversations",
        "description": (
            "Cerca conversazioni con filtri. Usa per investigare pattern specifici "
            "su un canale, uno stato, o un tipo di lead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Filtra per sorgente lead",
                    "enum": ["smartlead_outbound", "inbound_rank_checker", "reactivation"],
                },
                "status": {
                    "type": "string",
                    "description": "Stato conversazione",
                    "enum": ["active", "awaiting_human", "paused", "escalated", "converted", "dead"],
                },
                "stage": {
                    "type": "string",
                    "description": "Stage nel funnel",
                },
                "period": {
                    "type": "string",
                    "description": "Periodo temporale",
                    "enum": ["1d", "7d", "30d"],
                },
                "has_lead_reply": {
                    "type": "boolean",
                    "description": "Solo conversazioni dove il lead ha risposto",
                },
                "min_messages": {
                    "type": "integer",
                    "description": "Minimo numero di messaggi",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max risultati (default 20)",
                },
            },
        },
    },
    {
        "name": "get_conversation_detail",
        "description": (
            "Dettaglio completo di una conversazione: tutti i messaggi, strategia, "
            "contesto, storico feedback. Usa per capire cosa e' successo con un lead specifico."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conversation_id": {
                    "type": "string",
                    "description": "ID della conversazione",
                },
            },
            "required": ["conversation_id"],
        },
    },
    {
        "name": "search_calls",
        "description": (
            "Cerca chiamate del team umano con analisi strutturata di coaching. "
            "Include obiezioni emerse, tecniche di chiusura, score qualita'. "
            "Usa per capire come vanno le chiamate e come l'AI puo' preparare meglio i lead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["1d", "7d", "30d"],
                },
                "outcome": {
                    "type": "string",
                    "description": "Filtra per esito: interested, not-interested, callback, meeting-set, sale-made, voicemail, no-answer",
                },
                "min_duration": {
                    "type": "integer",
                    "description": "Durata minima in secondi",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max risultati (default 10)",
                },
            },
        },
    },
    {
        "name": "get_feedback_analysis",
        "description": (
            "Analisi dei feedback umani: cosa approvano, cosa modificano, cosa scartano e perche'. "
            "Include le modifiche specifiche fatte (tono, contenuto aggiunto/rimosso). "
            "Fondamentale per capire dove l'agente AI sbaglia."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Tipo di azione",
                    "enum": ["approved", "modified", "discarded"],
                },
                "period": {
                    "type": "string",
                    "enum": ["1d", "7d", "30d"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Max risultati (default 20)",
                },
            },
        },
    },
    {
        "name": "get_lead_timeline",
        "description": (
            "Storia completa di un lead specifico: tutte le conversazioni, messaggi, "
            "chiamate, feedback, task. Il tool per il deep-dive su un caso interessante."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Email del lead",
                },
            },
            "required": ["email"],
        },
    },
]

MAX_TOOL_CALLS = 12


async def _execute_tool(name: str, input_data: dict) -> dict:
    """Call a CRM internal endpoint for the given tool."""
    settings = get_settings()
    base = settings.menuchat_backend_url.rstrip("/")

    url_map = {
        "get_overview": "/api/internal/sm/overview",
        "search_conversations": "/api/internal/sm/conversations",
        "get_conversation_detail": f"/api/internal/sm/conversation/{input_data.pop('conversation_id', '')}",
        "search_calls": "/api/internal/sm/calls",
        "get_feedback_analysis": "/api/internal/sm/feedback",
        "get_lead_timeline": f"/api/internal/sm/lead-timeline/{input_data.pop('email', '')}",
    }

    path = url_map.get(name)
    if not path:
        return {"error": f"Unknown tool: {name}"}

    params = {}
    for k, v in input_data.items():
        if v is not None:
            snake = k.replace("_", "")
            camel = k
            for part_i, part in enumerate(k.split("_")):
                if part_i == 0:
                    camel = part
                else:
                    camel += part.capitalize()
            params[camel] = str(v) if isinstance(v, bool) else v

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.get(f"{base}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("SM tool %s failed: %s", name, e)
        return {"error": str(e)}


async def analyze_performance(trigger_data: dict) -> dict:
    """
    Run the Sales Manager agentic loop.

    The SM starts by calling get_overview, then investigates autonomously
    using tools, and finally produces structured output.
    """
    now_rome = datetime.now(tz=ZoneInfo("Europe/Rome"))
    settings = get_settings()
    client = _get_client()

    messages = [
        {
            "role": "user",
            "content": (
                f"TIMESTAMP: {now_rome.strftime('%A %d %B %Y, ore %H:%M')} (Roma)\n\n"
                "Inizia la tua analisi giornaliera del team. "
                "Usa get_overview per avere la panoramica, poi investiga in profondita' "
                "dove noti anomalie, pattern o opportunita'. "
                "Quando hai abbastanza informazioni, produci il tuo report JSON finale."
            ),
        }
    ]

    total_input_tokens = 0
    total_output_tokens = 0
    tool_calls_made = 0

    try:
        for iteration in range(MAX_TOOL_CALLS):
            async with client.messages.stream(
                model=settings.model_strategist,
                max_tokens=32000,
                temperature=1,
                thinking={"type": "enabled", "budget_tokens": 16000},
                system=SALES_MANAGER_SYSTEM,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                response = await stream.get_final_message()

            total_input_tokens += response.usage.input_tokens or 0
            total_output_tokens += response.usage.output_tokens or 0

            if response.stop_reason == "end_turn":
                break

            tool_results = []
            assistant_content = []

            for block in response.content:
                if block.type == "thinking":
                    assistant_content.append(block)
                    logger.info(
                        "SM thinking (iter %d): %s...",
                        iteration, block.thinking[:300],
                    )
                elif block.type == "text":
                    assistant_content.append(block)
                elif block.type == "tool_use":
                    assistant_content.append(block)
                    tool_calls_made += 1
                    logger.info("SM tool call: %s(%s)", block.name, json.dumps(block.input)[:200])
                    result = await _execute_tool(block.name, dict(block.input))
                    result_str = json.dumps(result, ensure_ascii=False, default=str)
                    if len(result_str) > 15000:
                        result_str = result_str[:15000] + '..."}'
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        output_text = ""
        thinking_text = ""
        final_msg = messages[-1] if messages[-1]["role"] == "assistant" else None

        if final_msg is None and response:
            for block in response.content:
                if block.type == "thinking":
                    thinking_text += block.thinking
                elif block.type == "text":
                    output_text += block.text
        else:
            for block in (final_msg or {}).get("content", []):
                if hasattr(block, "type"):
                    if block.type == "thinking":
                        thinking_text += block.thinking
                    elif block.type == "text":
                        output_text += block.text

        if not output_text and response:
            for block in response.content:
                if block.type == "text":
                    output_text += block.text

        parsed = json.loads(output_text[output_text.index("{"):output_text.rindex("}") + 1])

        logger.info(
            "Sales Manager complete: %d directives, %d alerts, %d tool calls, tokens=%d+%d",
            len(parsed.get("directives", [])),
            len(parsed.get("alerts", [])),
            tool_calls_made,
            total_input_tokens,
            total_output_tokens,
        )

        estimated_cost = round(
            (total_input_tokens * 15 + total_output_tokens * 75) / 1_000_000, 4
        )

        return {
            "directives": parsed.get("directives", []),
            "briefing": parsed.get("briefing", {}),
            "alerts": parsed.get("alerts", []),
            "performance": parsed.get("performance", {}),
            "thinking": thinking_text[:2000] if thinking_text else "",
            "tokens_used": total_input_tokens + total_output_tokens,
            "tool_calls_made": tool_calls_made,
            "estimated_cost_usd": estimated_cost,
        }
    except Exception as e:
        logger.error("Sales Manager failed: %s", e, exc_info=True)
        return {
            "directives": [],
            "briefing": {"headline": "Errore analisi", "summary": str(e)},
            "alerts": [{"severity": "warning", "message": f"Sales Manager error: {e}"}],
            "performance": {},
            "error": str(e),
        }
