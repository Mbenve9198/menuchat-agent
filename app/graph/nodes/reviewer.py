"""
Reviewer node — mostly deterministic checks + one focused LLM check.
The LLM's ONLY job: detect hallucinated data (names/numbers not in research).
Everything else is deterministic — no subjective judgments.
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

WRONG_PRODUCT_PHRASES = [
    re.compile(r"scansiona.*qr.*per.*recens", re.IGNORECASE),
    re.compile(r"qr.*code.*recensi", re.IGNORECASE),
    re.compile(r"clienti\s+soddisfatti\s+scansion", re.IGNORECASE),
    re.compile(r"scansion.*per\s+lasciare", re.IGNORECASE),
]

BANNED_PLATFORMS = ["tripadvisor", "trip advisor", "yelp", "trustpilot"]


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


def _deterministic_checks(draft: str, strategy: dict) -> list[str]:
    """Fast deterministic checks — no LLM needed."""
    violations = []

    # PII
    for pattern, label in PII_PATTERNS:
        if pattern.search(draft):
            violations.append(f"PII: {label} nel testo")
    for email in INTERNAL_EMAILS:
        if email.lower() in draft.lower():
            violations.append(f"Email interna esposta: {email}")

    # Banned platforms
    draft_lower = draft.lower()
    for platform in BANNED_PLATFORMS:
        if platform in draft_lower:
            violations.append(f"Piattaforma vietata menzionata: {platform}")

    # Wrong product description
    for pattern in WRONG_PRODUCT_PHRASES:
        if pattern.search(draft):
            violations.append("Errore prodotto: il QR è per il MENU, non per le recensioni")
            break

    # Word count
    max_words = strategy.get("max_words", 120)
    word_count = len(draft.split())
    if word_count > max_words + 20:
        violations.append(f"Troppo lungo: {word_count} parole (max {max_words})")

    return violations


HALLUCINATION_CHECK_PROMPT = """Controlla se questo messaggio di vendita cita dati INVENTATI.

Confronta SOLO nomi di ristoranti, numeri di recensioni, posizioni su Google Maps, e statistiche 
con i DATI VERIFICATI sotto. Se il messaggio cita un ristorante, un numero o una statistica 
che NON appare nei dati verificati, segnalalo.

NON segnalare:
- Inferenze ragionevoli dal contesto (es: se il lead dice "abbiamo chi ci segue", il messaggio può dire "il vostro attuale supporto")
- Arrotondamenti o parafrasi di numeri presenti nei dati
- Descrizioni generiche del prodotto/servizio
- Il tono o lo stile del messaggio — non è compito tuo giudicarlo

Segnala SOLO dati concreti inventati (nomi, numeri, statistiche non verificabili).

DATI VERIFICATI:
{data_summary}

Rispondi con JSON: {{"hallucinations_found": false}} oppure {{"hallucinations_found": true, "details": "cosa è inventato"}}"""


async def reviewer_node(state: AgentState) -> dict:
    draft = state.get("draft") or ""
    strategy = state.get("strategy") or {}
    research = state.get("research") or {}
    review_attempts = state.get("review_attempts", 0)

    # Step 1: deterministic checks (instant, no LLM)
    det_violations = _deterministic_checks(draft, strategy)
    if det_violations:
        logger.info("Reviewer deterministic FAIL: %s", det_violations)
        return {
            "review_result": {"pass": False, "violations": det_violations, "feedback": " ".join(det_violations)},
            "review_attempts": review_attempts + 1,
        }

    # Step 2: LLM hallucination check (only job for Haiku)
    data_summary = research.get("available_data_summary", "")
    if not data_summary:
        logger.info("Reviewer: no data summary, auto-pass")
        return {
            "review_result": {"pass": True, "violations": [], "feedback": ""},
            "review_attempts": review_attempts + 1,
        }

    prompt = HALLUCINATION_CHECK_PROMPT.replace("{data_summary}", data_summary)

    settings = get_settings()
    client = _get_client()

    try:
        resp = await client.messages.create(
            model=settings.model_reviewer,
            max_tokens=500,
            temperature=0,
            system=prompt,
            messages=[{"role": "user", "content": f"MESSAGGIO:\n\n{draft}"}],
        )

        text = resp.content[0].text.strip()
        parsed = json.loads(text[text.index("{"):text.rindex("}") + 1])

        if parsed.get("hallucinations_found"):
            details = parsed.get("details", "Dati inventati rilevati")
            logger.info("Reviewer: hallucination detected — %s", details)
            return {
                "review_result": {"pass": False, "violations": [f"Dato inventato: {details}"], "feedback": f"Rimuovi o correggi: {details}"},
                "review_attempts": review_attempts + 1,
                "total_input_tokens": state.get("total_input_tokens", 0) + (resp.usage.input_tokens or 0),
                "total_output_tokens": state.get("total_output_tokens", 0) + (resp.usage.output_tokens or 0),
            }

        logger.info("Reviewer: PASS (no hallucinations)")
        return {
            "review_result": {"pass": True, "violations": [], "feedback": ""},
            "review_attempts": review_attempts + 1,
            "total_input_tokens": state.get("total_input_tokens", 0) + (resp.usage.input_tokens or 0),
            "total_output_tokens": state.get("total_output_tokens", 0) + (resp.usage.output_tokens or 0),
        }

    except Exception as e:
        logger.warning("Reviewer error, auto-pass: %s", e)
        return {
            "review_result": {"pass": True, "violations": [], "feedback": ""},
            "review_attempts": review_attempts + 1,
        }
