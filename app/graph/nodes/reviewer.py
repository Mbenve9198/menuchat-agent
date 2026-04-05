"""
Reviewer node — Haiku 4.5 + deterministic PII scanner.
Validates the draft against rules, data accuracy, and PII leaks.
"""

import json
import logging
import re

import anthropic

from app.config import get_settings
from app.graph.state import AgentState

logger = logging.getLogger("agent-service.nodes.reviewer")

_client: anthropic.AsyncAnthropic | None = None

PII_PATTERNS = [
    (re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"), "codice_fiscale"),
    (re.compile(r"\b[A-Z]{2}\d{2}[A-Z]\d{10,22}\b"), "iban"),
    (re.compile(r"\bsk-ant-[a-zA-Z0-9\-]+\b"), "api_key"),
    (re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE), "password"),
]

INTERNAL_EMAILS = ["marco@menuchat.com", "federico@menuchat.it", "team@menuchat.it"]


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


def _scan_pii(text: str) -> list[str]:
    violations = []
    for pattern, label in PII_PATTERNS:
        if pattern.search(text):
            violations.append(f"PII leak: {label} detected in draft")
    for email in INTERNAL_EMAILS:
        if email.lower() in text.lower():
            violations.append(f"Internal email leaked: {email}")
    return violations


def _build_reviewer_prompt(strategy: dict, research: dict, lead_source: str, stage: str) -> str:
    is_first = stage == "initial_reply" and lead_source in ("inbound_rank_checker", "smartlead_outbound")
    max_words = strategy.get("max_words", 100)
    do_not = strategy.get("do_not", [])
    data_summary = research.get("available_data_summary", "N/A")

    return f"""Sei un quality reviewer per messaggi di vendita. Controlla il messaggio contro le regole.

REGOLE (se violate = FAIL):
1. NON deve contenere descrizione DETTAGLIATA del meccanismo tecnico (QR code, WhatsApp bot, filtro recensioni). Frasi generiche SONO OK: "sistema automatico per raccogliere recensioni".
2. {"E' un PRIMO CONTATTO: NON deve contenere il PREZZO NUMERICO (euro, cifre). 'Prova gratuita' e '2 settimane gratis' SONO OK." if is_first else "Il prezzo può essere menzionato."}
3. NON deve menzionare videochiamate, Zoom, Google Meet. "Chiamata al telefono" È OK.
4. NON deve superare {max_words} parole. Conta attentamente.
5. NON deve contenere dati inventati. Confronta OGNI nome, numero e statistica con i DATI DISPONIBILI sotto. Se non è presente → ALLUCINAZIONE = FAIL.
6. NON deve attribuire al lead frasi che non ha detto.
7. DEVE avere una CTA chiara alla fine.
8. DEVE essere firmato col nome.
9. Il tono deve sembrare umano, non da bot AI.

PROIBIZIONI DAL PIANO:
{chr(10).join('- ' + d for d in do_not)}

DATI DISPONIBILI (qualsiasi dato non presente qui è inventato):
{data_summary}

Rispondi SOLO con JSON:
{{"pass": true, "violations": [], "feedback": ""}}
oppure
{{"pass": false, "violations": ["regola X violata: dettaglio"], "feedback": "Cosa correggere"}}"""


async def reviewer_node(state: AgentState) -> dict:
    draft = state.get("draft", "")
    strategy = state.get("strategy", {})
    research = state.get("research", {})
    request = state["request"]
    review_attempts = state.get("review_attempts", 0)

    lead_source = getattr(request, "lead_source", "smartlead_outbound")
    stage = getattr(request, "stage", "initial_reply")

    pii_violations = _scan_pii(draft)
    if pii_violations:
        logger.warning("PII detected in draft: %s", pii_violations)
        return {
            "review_result": {"pass": False, "violations": pii_violations, "feedback": "CRITICO: dati sensibili nel testo. Rimuoverli."},
            "review_attempts": review_attempts + 1,
        }

    system_prompt = _build_reviewer_prompt(strategy, research, lead_source, stage)

    settings = get_settings()
    client = _get_client()

    try:
        resp = await client.messages.create(
            model=settings.model_reviewer,
            max_tokens=settings.reviewer_max_tokens,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": f"MESSAGGIO DA CONTROLLARE:\n\n{draft}"}],
        )

        text = resp.content[0].text.strip()
        parsed = json.loads(text[text.index("{"):text.rindex("}") + 1])

        result = {
            "pass": parsed.get("pass", False),
            "violations": parsed.get("violations", []),
            "feedback": parsed.get("feedback", ""),
        }

        logger.info("Reviewer: pass=%s violations=%s", result["pass"], result["violations"])

        return {
            "review_result": result,
            "review_attempts": review_attempts + 1,
            "total_input_tokens": state.get("total_input_tokens", 0) + (resp.usage.input_tokens or 0),
            "total_output_tokens": state.get("total_output_tokens", 0) + (resp.usage.output_tokens or 0),
        }
    except Exception as e:
        logger.warning("Reviewer parse error, failing safe: %s", e)
        return {
            "review_result": {"pass": False, "violations": ["reviewer_parse_error"], "feedback": "Errore nel parsing della review."},
            "review_attempts": review_attempts + 1,
        }
