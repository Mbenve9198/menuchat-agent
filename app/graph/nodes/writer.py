"""
Writer node — Sonnet 4.6, low temperature.
Transforms the strategist's plan into natural Italian sales copy.
"""

import json
import logging

import anthropic

from app.config import get_settings
from app.graph.state import AgentState

logger = logging.getLogger("agent-service.nodes.writer")

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


def _build_writer_system(identity, review_feedback: str | None = None) -> str:
    name = identity.name if hasattr(identity, "name") else identity.get("name", "Marco")
    surname = identity.surname if hasattr(identity, "surname") else identity.get("surname", "Benvenuti")
    role = identity.role if hasattr(identity, "role") else identity.get("role", "co-founder")

    prompt = f"""Sei {name} {surname}, {role} di MenuChat. Scrivi un messaggio a un ristoratore italiano.

Riceverai un piano dallo strategist con: la strategia, le istruzioni per il messaggio, i dati da citare, il tono, e le cose da NON fare.

COME SCRIVI:
- Come un messaggio tra colleghi che lavorano. Diretto, amichevole, zero formalità.
- Mai "Gentilissimo", mai "Cordiali saluti". Chiudi con "A presto" o col nome.
- Firma solo "{name}".
- NON inventare MAI dati che non sono nel piano o nei dati forniti.
- NON attribuire al lead frasi che non ha detto.
- NON menzionare MAI TripAdvisor, Yelp o piattaforme diverse da Google.
- Il QR code è per il MENU, NON per le recensioni. La richiesta di recensione arriva DOPO il pasto.

Scrivi SOLO il testo del messaggio, nient'altro."""

    if review_feedback:
        prompt += f"\n\nATTENZIONE — IL REVIEWER HA TROVATO PROBLEMI NELLA BOZZA PRECEDENTE:\n{review_feedback}\nRiscrivi correggendo TUTTI i problemi."

    return prompt


def _build_writer_input(strategy: dict, research: dict, messages: list) -> str:
    parts = []

    plan = strategy.get("message_plan") or strategy.get("strategy", "")
    reasoning = strategy.get("reasoning", "")
    data_to_cite = strategy.get("data_to_cite", [])
    tone = strategy.get("tone_description") or strategy.get("tone", "amichevole e diretto")
    max_words = strategy.get("max_words", 100)
    do_not = strategy.get("do_not", [])

    parts.append(f"STRATEGIA SCELTA:\n{reasoning}\n")
    parts.append(f"ISTRUZIONI PER IL MESSAGGIO:\n{plan}\n")

    if data_to_cite:
        parts.append("DATI DA CITARE (usa questi, sono verificati):")
        for d in data_to_cite:
            parts.append(f"  • {d}")
        parts.append("")

    parts.append(f"TONO: {tone}")
    parts.append(f"MAX PAROLE: {max_words}")

    if do_not:
        parts.append("NON FARE:")
        for d in do_not:
            parts.append(f"  • {d}")
        parts.append("")

    if messages:
        recent = messages[-6:] if len(messages) > 6 else messages
        parts.append("ULTIMI MESSAGGI DELLA CONVERSAZIONE:")
        for m in recent:
            role = m.role if hasattr(m, "role") else m.get("role", "?")
            content = m.content if hasattr(m, "content") else m.get("content", "")
            parts.append(f"[{role.upper()}]: {content[:300]}")
        parts.append("")

    contact = research.get("contact", {})
    parts.append(f"LEAD: {contact.get('name', 'N/A')} | {contact.get('city', '')} | Tel: {contact.get('phone', 'non disponibile')}")

    parts.append(f"\nScrivi il messaggio. Massimo {max_words} parole.")

    return "\n".join(parts)


async def writer_node(state: AgentState) -> dict:
    request = state["request"]
    strategy = state.get("strategy") or {}
    research = state.get("research") or {}
    review_feedback = state.get("review_result", {}).get("feedback") if state.get("review_result") else None
    review_attempts = state.get("review_attempts", 0)

    identity = getattr(request, "agent_identity", None) or {"name": "Marco", "surname": "Benvenuti", "role": "co-founder"}
    messages = getattr(request, "messages", []) or []

    system_prompt = _build_writer_system(identity, review_feedback if review_attempts > 0 else None)
    user_input = _build_writer_input(strategy, research, messages)

    settings = get_settings()
    client = _get_client()

    resp = await client.messages.create(
        model=settings.model_writer,
        max_tokens=settings.writer_max_tokens,
        temperature=0.4,
        system=system_prompt,
        messages=[{"role": "user", "content": user_input}],
    )

    draft = resp.content[0].text.strip()
    max_words = strategy.get("max_words", 100)

    logger.info("Writer: %d words (max %d), retry=%d", len(draft.split()), max_words, review_attempts)

    return {
        "draft": draft,
        "total_input_tokens": state.get("total_input_tokens", 0) + (resp.usage.input_tokens or 0),
        "total_output_tokens": state.get("total_output_tokens", 0) + (resp.usage.output_tokens or 0),
    }
