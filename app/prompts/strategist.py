"""
Strategist prompt — gives Opus understanding and freedom, not scripts and menus.
"""

from app.knowledge.product import PRODUCT_KNOWLEDGE
from app.knowledge.strategies import STRATEGIC_PRINCIPLES
from app.knowledge.proactive import PROACTIVE_KNOWLEDGE


def build_strategist_system_prompt() -> str:
    return f"""Sei il cervello strategico del team vendita MenuChat.

Il tuo obiettivo: decidere la strategia migliore per convincere QUESTO SPECIFICO lead a prenotare una chiamata di 5 minuti con noi.

Non hai script da seguire. Hai COMPRENSIONE del business e DATI dal ricercatore. Ragiona liberamente.

## IL MONDO DEL RISTORATORE

PAIN POINT PROFONDI:
- "Il ristorante di fronte ha 500 recensioni e io 80 — i clienti vanno li"
- "Ogni recensione negativa mi rovina la media e non posso farci niente"
- "So che i clienti sono contenti ma nessuno lascia recensioni"
- "Pago un'agenzia e non vedo risultati concreti sulle recensioni"
- "Non ho tempo di chiedere recensioni ai clienti uno per uno"

DREAM OUTCOME:
- Essere il PRIMO risultato quando qualcuno cerca "ristorante + la mia zona"
- Avere cosi tante recensioni positive che le negative spariscono
- Un sistema che funziona DA SOLO senza fare niente
- Vedere clienti arrivare perche ti hanno trovato su Google

COME MENUCHAT COLMA IL GAP — IL MECCANISMO:
Il QR code e per il MENU (tutti i clienti lo scansionano per vedere i piatti). Dopo il pasto, il sistema chiede la recensione via WhatsApp. Le positive vanno su Google, le negative restano private.

Questo produce un effetto a catena:
- Ogni giorno entrano nuove recensioni positive → le negative vengono sommerse dal volume
- Il volume costante fa salire il ranking su Google Maps → piu visibilita
- Piu visibilita → piu clienti → piu recensioni → ciclo virtuoso
- In 6 mesi un ristorante con 200 coperti/giorno puo raccogliere 600-1000 recensioni, diventando praticamente inarrivabile nella sua zona

E un unico sistema che risolve piu problemi contemporaneamente: reputazione, visibilita, e acquisizione clienti. Non sono argomenti separati — sono lo stesso meccanismo.

Prova gratis 2 settimane, zero rischio. ~100 euro/mese (1.290 euro/anno).

{PRODUCT_KNOWLEDGE}

{STRATEGIC_PRINCIPLES}

{PROACTIVE_KNOWLEDGE}

## COSA DEVI PRODURRE

Decidi:
1. Quale STRATEGIA usare per questo lead (non scegliere da un menu — inventala per la situazione)
2. COSA deve dire il messaggio e QUALI DATI citare (dal research)
3. Il TONO giusto per questa persona specifica
4. Se servono AZIONI FUTURE (follow-up, ibernazione, escalation)

## OUTPUT

Rispondi SOLO con JSON valido:
{{
  "reasoning": "Il tuo ragionamento completo: chi è questo lead, cosa vuole, cosa teme, perché hai scelto questa strategia, cosa vuoi ottenere (scrivi quanto serve)",
  "strategy": "Descrizione libera della strategia scelta",
  "message_plan": "Istruzioni per il writer: cosa dire, in quale ordine, come dirlo, quali dati usare. Sii specifico ma non rigido — il writer sa scrivere, tu gli dai la direzione.",
  "data_to_cite": ["dato specifico 1 dal research", "dato specifico 2", "..."],
  "tone_description": "Descrizione libera del tono (es: 'diretto e amichevole, come un collega che ti dà un consiglio')",
  "max_words": 100,
  "do_not": ["cosa NON fare in questo messaggio specifico"],
  "channel": "email | whatsapp",
  "future_actions": [
    {{"type": "schedule_task", "task_type": "follow_up_no_reply", "delay_days": 3, "reason": "motivo"}}
  ],
  "escalate_human": false,
  "hibernate": null
}}

Se il lead indica un periodo futuro (es: "riapriamo a maggio"):
{{
  ...
  "hibernate": {{
    "wake_at": "2026-04-25T09:00:00+02:00",
    "task_type": "seasonal_reactivation",
    "reason": "Motivo dell'ibernazione"
  }}
}}
"""


def build_strategist_user_input(
    lead_message: str,
    research: dict,
    conversation_context: str,
    episodic_examples: list[dict],
    contact_memories: list[dict] | None = None,
) -> str:
    parts = [f'MESSAGGIO DEL LEAD:\n"{lead_message}"\n']

    crm_context = research.get("crm_context")
    if crm_context:
        parts.append(f"CONTESTO CRM — STORICO RELAZIONE CON QUESTO LEAD:\n{crm_context}\n")

    data_summary = research.get("available_data_summary", "")
    if data_summary:
        parts.append(f"DATI RACCOLTI DAL RICERCATORE:\n{data_summary}")

    thread = research.get("email_thread", [])
    if thread:
        parts.append("\nSTORICO EMAIL:")
        for e in thread:
            label = "NOI" if e.get("type") == "SENT" else "LEAD"
            parts.append(f"[{label}] {e.get('subject', '')}: {e.get('body', '')[:300]}")

    if research.get("has_digital_menu") is True:
        parts.append("\nIl lead ha GIÀ un menu digitale.")
    elif research.get("has_digital_menu") is False:
        parts.append("\nIl lead NON ha menu digitale.")

    parts.append(f"\n{conversation_context}")

    if episodic_examples:
        parts.append("\nMEMORIA EPISODICA — ESPERIENZE PASSATE CON LEAD SIMILI:")
        for i, ep in enumerate(episodic_examples[:3], 1):
            outcome = ep.get("outcome", "?")
            strategy = ep.get("strategy", "?")
            lead_p = ep.get("lead_profile", {})
            lead_desc = f"{lead_p.get('category', '?')} ({lead_p.get('city', '?')})"

            parts.append(f"\n  Episodio {i} [{outcome.upper()}] — {lead_desc}:")
            parts.append(f"    Strategia: {strategy}")
            if ep.get("situation"):
                parts.append(f"    Situazione: {ep['situation'][:200]}")
            if ep.get("objections"):
                parts.append(f"    Obiezioni: {', '.join(ep['objections'][:3])}")

            edits = ep.get("human_edits", {})
            if outcome == "modified" and edits:
                if edits.get("modifications"):
                    mods = edits["modifications"]
                    if mods.get("toneChange"):
                        parts.append(f"    Correzione tono: {mods['toneChange']}")
                    if mods.get("addedContent"):
                        parts.append(f"    Aggiunto: {mods['addedContent'][:150]}")
                    if mods.get("removedContent"):
                        parts.append(f"    Rimosso: {mods['removedContent'][:150]}")
            elif outcome == "discarded" and edits:
                reason = edits.get("discard_reason", "")
                notes = edits.get("discard_notes", "")
                if reason:
                    parts.append(f"    Motivo scarto: {reason}")
                if notes:
                    parts.append(f"    Note: {notes[:150]}")

    if contact_memories:
        parts.append("\nMEMORIA AGENTE — LE TUE OSSERVAZIONI PRECEDENTI SU QUESTO LEAD:")
        for mem in contact_memories[:5]:
            date = mem.get("stored_at", "")[:10]
            obs = mem.get("observation", "")
            strat = mem.get("strategy_used", "")
            outcome = mem.get("outcome", "")
            line = f"  [{date}] {obs[:300]}"
            if strat:
                line += f" (strategia: {strat[:80]})"
            if outcome:
                line += f" → {outcome}"
            parts.append(line)

    return "\n".join(parts)
