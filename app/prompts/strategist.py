"""
Strategist prompt assembly — builds the full system prompt for Opus 4.6.
Injects knowledge base, research data, conversation context, and episodic examples.
"""

from app.knowledge.product import PRODUCT_KNOWLEDGE
from app.knowledge.patterns import RESPONSE_PATTERNS
from app.knowledge.strategies import STRATEGIC_PRINCIPLES
from app.knowledge.objections import OBJECTION_PRINCIPLES


def build_strategist_system_prompt() -> str:
    return f"""Sei il cervello strategico del team di vendita MenuChat.
Il tuo compito: analizzare il messaggio del lead e i dati disponibili, poi decidere la STRATEGIA MIGLIORE.
NON scrivi il messaggio — decidi COSA dire, COME dirlo, e QUALI dati usare.

NON seguire script. RAGIONA. Usa il thinking esteso per:
1. Capire CHI è questo lead e COSA vuole (o teme)
2. Analizzare i dati di ricerca per trovare le LEVE più forti
3. Decidere l'ANGOLO migliore (problema, dream outcome, social proof, empatia)
4. Definire il PIANO dettagliato per il writer
5. Decidere se servono azioni future (follow-up, hibernate, escalation)

{PRODUCT_KNOWLEDGE}

{RESPONSE_PATTERNS}

{STRATEGIC_PRINCIPLES}

{OBJECTION_PRINCIPLES}

## OUTPUT

Rispondi SOLO con JSON valido:
{{
  "approach": "pain_agitation | dream_outcome | social_proof | objection_reframe | empathy_disarm | insight_drop | ugly_spear | system_action | escalate_human | hibernate",
  "reasoning": "Spiegazione della strategia scelta — perché questo angolo, cosa abbiamo trovato nella ricerca, cosa vogliamo ottenere (max 200 parole)",
  "message_structure": [
    {{"section": "opener", "instruction": "cosa dire nell'apertura"}},
    {{"section": "body", "instruction": "quale leva usare, quali dati citare"}},
    {{"section": "proof", "instruction": "quale social proof usare (nome, dati, menuUrl)"}},
    {{"section": "cta", "instruction": "come chiedere il telefono/appuntamento"}}
  ],
  "data_to_include": {{
    "competitor_name": "nome competitor da citare o null",
    "similar_client": {{"name": "...", "data": "...", "menu_url": "..."}} ,
    "ranking_position": "posizione da citare o null",
    "negative_reviews_leverage": true/false,
    "projected_reviews": "stima da citare o null"
  }},
  "tone": "consultivo | diretto | amichevole | empatico | sfida_gentile",
  "max_words": 100,
  "do_not": ["lista di cose da NON fare assolutamente"],
  "channel": "email | whatsapp",
  "future_actions": [
    {{"type": "schedule_task | hibernate_workflow", "task_type": "follow_up_no_reply | break_up_email | seasonal_reactivation | human_task", "delay_days": 3, "reason": "motivo"}}
  ],
  "escalate_human": false,
  "hibernate": null
}}

Se decidi di ibernare il workflow (es: lead dice "riapriamo a maggio"):
{{
  "approach": "hibernate",
  "reasoning": "Il lead ha indicato riapertura a maggio. Iberno il workflow per riattivazione.",
  "hibernate": {{
    "wake_at": "2026-04-25T09:00:00+02:00",
    "task_type": "seasonal_reactivation",
    "reason": "Lead stagionale, riapertura maggio"
  }},
  ...
}}
"""


def build_strategist_user_input(lead_message: str, research: dict, conversation_context: str, episodic_examples: list[dict]) -> str:
    parts = [f'MESSAGGIO DEL LEAD:\n"{lead_message}"\n']

    contact = research.get("contact", {})
    parts.append("DATI DISPONIBILI:")
    parts.append(f"- Ristorante: {contact.get('name', 'N/A')}")
    parts.append(f"- Città: {contact.get('city', 'N/A')}")
    if contact.get("phone"):
        parts.append(f"- Telefono: {contact['phone']}")
    if contact.get("rating"):
        parts.append(f"- Rating Google: {contact['rating']}/5")
    if contact.get("reviews"):
        parts.append(f"- Recensioni Google: {contact['reviews']}")

    ranking = research.get("ranking")
    if ranking and ranking.get("main_rank"):
        parts.append(f"\nRANK CHECKER DATA:")
        parts.append(f"- Keyword: \"{ranking.get('keyword')}\"")
        parts.append(f"- Posizione: {ranking['main_rank']}°")
        if ranking.get("competitors_ahead"):
            parts.append(f"- Competitor davanti: {ranking['competitors_ahead']}")
        if ranking.get("estimated_lost_customers"):
            parts.append(f"- Clienti persi/settimana: ~{ranking['estimated_lost_customers']}")
        if ranking.get("daily_covers"):
            parts.append(f"- Coperti/giorno: {ranking['daily_covers']}")

    proj = research.get("projected_reviews_2_weeks")
    if proj:
        parts.append(f"- Stima recensioni in 2 settimane prova: ~{proj}")

    competitors = research.get("competitors", [])
    if competitors:
        parts.append("\nCOMPETITOR:")
        for c in competitors[:5]:
            parts.append(f"- {c['name']}: pos {c['rank']}, {c.get('rating', '?')} stelle, {c.get('reviews', '?')} rec")

    neg = research.get("negative_reviews_summary")
    if neg:
        parts.append(f"\nRECENSIONI NEGATIVE RECENTI:\n{neg}")

    similar = research.get("similar_clients", [])
    if similar:
        parts.append("\nCLIENTI MENUCHAT REALI (usa come social proof — questi sono dati VERIFICATI):")
        for c in similar[:3]:
            parts.append(
                f"- {c.get('name')} ({c.get('city')}): ha raccolto {c.get('reviews_gained')} recensioni CON MENUCHAT "
                f"in {c.get('months_active')} mesi (media {c.get('avg_reviews_per_month', '?')}/mese). "
                f"Partiva da {c.get('initial_reviews', '?')} recensioni, ora ne ha {c.get('current_reviews', '?')}."
            )
            if c.get("menu_url"):
                parts.append(f"  → CONDIVIDI questo link al menu: {c['menu_url']} (il lead può vederlo con i propri occhi)")
            if c.get("menu_item_count"):
                parts.append(f"  → Menu con {c['menu_item_count']} piatti")
    else:
        fallback = research.get("fallback_case_studies", [])
        if fallback:
            parts.append("\nCASE STUDY GENERICI:")
            for c in fallback[:3]:
                parts.append(f"- {c['name']} ({c['city']}): {c['result']}")

    thread = research.get("email_thread", [])
    if thread:
        parts.append("\nSTORICO EMAIL (cosa abbiamo scritto e cosa ha risposto il lead):")
        for e in thread:
            label = "NOI" if e["type"] == "SENT" else "LEAD"
            parts.append(f"[{label}] {e.get('subject', '')}: {e['body'][:300]}")

    if research.get("has_digital_menu") is True:
        parts.append("\nMENU DIGITALE: Il lead ha già un menu digitale — è a un passo dal sistema completo.")
    elif research.get("has_digital_menu") is False:
        parts.append("\nMENU DIGITALE: NON ha menu digitale.")

    parts.append(f"\n{conversation_context}")

    if episodic_examples:
        parts.append("\nEPISODI VINCENTI SIMILI (strategie che hanno funzionato in passato):")
        for ep in episodic_examples[:3]:
            parts.append(f"- Obiezione: {ep.get('objection', 'N/A')} → Strategia: {ep.get('strategy', 'N/A')} → Risultato: {ep.get('outcome', 'N/A')}")

    return "\n".join(parts)
