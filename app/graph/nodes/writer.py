"""
Writer node — Sonnet 4.6, low temperature.
Transforms the strategist's JSON plan into natural Italian sales copy.
"""

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

    prompt = f"""Sei {name} {surname}, {role} di MenuChat. Scrivi messaggi a ristoratori italiani.

TONO: come un messaggio tra colleghi che lavorano. Diretto, amichevole, zero formalità.
Mai "Gentilissimo", mai "Cordiali saluti". Chiudi con "A presto" o col nome.

Riceverai un PIANO JSON con: approach, message_structure, data_to_include, tone, max_words, do_not.

REGOLE CRITICHE:
- Massimo {{max_words}} parole (dal piano). Conta le parole — NON sforare.
- Segui il piano alla lettera. Le voci in "do_not" sono PROIBIZIONI ASSOLUTE.
- Se il piano ha social proof con dati, DEVI citarli nel messaggio.
- Se il piano ha CTA "confirm_number", DEVI includere il numero e chiedere conferma.
- Firma solo "{name}".
- NON inventare MAI informazioni che non sono nel piano o nei dati forniti.
- NON attribuire al lead frasi che non ha detto.

Scrivi SOLO il testo del messaggio, nient'altro."""

    if review_feedback:
        prompt += f"\n\nATTENZIONE — IL REVIEWER HA TROVATO PROBLEMI NELLA BOZZA PRECEDENTE:\n{review_feedback}\nRiscrivi il messaggio correggendo TUTTI i problemi segnalati."

    return prompt


def _build_writer_input(strategy: dict, research: dict, messages: list) -> str:
    import json
    parts = [f"PIANO STRATEGICO:\n{json.dumps(strategy, ensure_ascii=False, indent=2)}\n"]

    if messages:
        recent = messages[-6:] if len(messages) > 6 else messages
        parts.append("ULTIMI MESSAGGI:")
        for m in recent:
            role = m.role if hasattr(m, "role") else m.get("role", "?")
            content = m.content if hasattr(m, "content") else m.get("content", "")
            parts.append(f"[{role.upper()}]: {content[:300]}")
        parts.append("")

    contact = research.get("contact", {})
    parts.append(f"DATI LEAD:\n- Nome: {contact.get('name', 'N/A')}")
    if contact.get("phone"):
        parts.append(f"- Telefono: {contact['phone']}")
    if contact.get("city"):
        parts.append(f"- Città: {contact['city']}")

    max_words = strategy.get("max_words", 100)
    parts.append(f"\nScrivi il messaggio ora. Massimo {max_words} parole.")

    return "\n".join(parts)


async def writer_node(state: AgentState) -> dict:
    request = state["request"]
    strategy = state.get("strategy", {})
    research = state.get("research", {})
    review_feedback = state.get("review_result", {}).get("feedback") if state.get("review_result") else None
    review_attempts = state.get("review_attempts", 0)

    identity = getattr(request, "agent_identity", None) or {"name": "Marco", "surname": "Benvenuti", "role": "co-founder"}
    messages = getattr(request, "messages", []) or []

    system_prompt = _build_writer_system(identity, review_feedback if review_attempts > 0 else None)
    max_words = strategy.get("max_words", 100)
    system_prompt = system_prompt.replace("{max_words}", str(max_words))

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
    word_count = len(draft.split())

    logger.info("Writer: %d words (max %d), retry=%d", word_count, max_words, review_attempts)

    return {
        "draft": draft,
        "total_input_tokens": state.get("total_input_tokens", 0) + (resp.usage.input_tokens or 0),
        "total_output_tokens": state.get("total_output_tokens", 0) + (resp.usage.output_tokens or 0),
    }
