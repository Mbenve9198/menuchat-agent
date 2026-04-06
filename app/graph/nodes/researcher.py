"""
Agentic Researcher node — Sonnet 4.6 with tool-use loop.
Autonomously decides what to search for, when to dig deeper, and when it has enough.
"""

import json
import logging
from typing import Any

import anthropic

from app.config import get_settings
from app.graph.state import AgentState, ResearchData
from app.prompts.researcher import RESEARCHER_SYSTEM_PROMPT, RESEARCHER_TOOLS
from app.tools.serpapi_client import research_business, fetch_reviews, check_ranking, research_competitor
from app.tools.menuchat_client import search_similar_clients
from app.tools.smartlead_client import fetch_message_history

logger = logging.getLogger("agent-service.nodes.researcher")

MAX_ROUNDS = 15

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


async def _execute_tool(name: str, params: dict) -> Any:
    """Route a tool call to the actual implementation."""
    try:
        if name == "research_business":
            return await research_business(
                place_id=params.get("place_id"),
                business_name=params.get("business_name"),
                city=params.get("city"),
            )
        elif name == "fetch_reviews":
            return await fetch_reviews(
                params["place_id"],
                next_page_token=params.get("next_page_token"),
            )
        elif name == "search_similar_clients":
            return await search_similar_clients(
                params.get("cuisine_type", ""),
                city=params.get("city"),
            )
        elif name == "fetch_email_thread":
            return await fetch_message_history(
                params["campaign_id"],
                params["lead_id"],
            )
        elif name == "check_ranking":
            return await check_ranking(
                params["keyword"],
                latitude=params["latitude"],
                longitude=params["longitude"],
                place_id=params.get("place_id"),
                restaurant_name=params.get("restaurant_name"),
            )
        elif name == "research_competitor":
            return await research_competitor(
                place_id=params.get("place_id"),
                competitor_name=params.get("competitor_name"),
                city=params.get("city"),
            )
        elif name == "done":
            return {"status": "done", "summary": params.get("summary", ""), "key_findings": params.get("key_findings", [])}
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return {"error": str(e)}


def _build_user_context(request, contact: dict, rc_data: dict) -> str:
    """Build the context message that the researcher agent receives."""
    parts = []

    lead_message = getattr(request, "lead_message", "") or ""
    if lead_message:
        parts.append(f'MESSAGGIO DEL LEAD:\n"{lead_message}"')
    else:
        task_type = getattr(request, "task_type", "")
        task_ctx = getattr(request, "task_context", {}) or {}
        parts.append(f"AZIONE PROATTIVA: {task_type}. Motivo: {task_ctx.get('reason', 'N/A')}")

    parts.append(f"\nCONTATTO:")
    parts.append(f"- Nome: {contact.get('name', 'N/A')}")
    parts.append(f"- Email: {contact.get('email', 'N/A')}")
    if contact.get("phone"):
        parts.append(f"- Telefono: {contact['phone']}")
    parts.append(f"- Città: {contact.get('city', 'N/A')}")
    if contact.get("rating"):
        parts.append(f"- Rating Google: {contact['rating']}/5")
    if contact.get("reviews"):
        parts.append(f"- Recensioni Google: {contact['reviews']}")
    if contact.get("category"):
        parts.append(f"- Tipo: {contact['category']}")
    if contact.get("website"):
        parts.append(f"- Sito: {contact['website']}")
    parts.append(f"- Fonte: {contact.get('source', 'N/A')}")
    if contact.get("contact_person"):
        parts.append(f"- Persona di contatto: {contact['contact_person']}")
    if contact.get("place_id"):
        parts.append(f"- Google Place ID: {contact['place_id']} (usa questo per cercare su Google Maps, e molto piu preciso del nome)")
    if contact.get("coordinates"):
        coords = contact["coordinates"]
        lat = coords.get("lat") or coords.get("latitude")
        lng = coords.get("lng") or coords.get("longitude")
        if lat and lng:
            parts.append(f"- Coordinate: lat={lat}, lng={lng} (usa queste per il rank check)")
    if contact.get("call_requested"):
        pref = contact.get("call_preference", "")
        parts.append(f"- IL LEAD HA GIA RICHIESTO UNA CHIAMATA (preferenza: {pref})")

    if rc_data:
        parts.append("\nDATI RANK CHECKER (il lead ha fatto un audit sul nostro sito — questi dati li ha GIA VISTI):")
        if rc_data.get("placeId"):
            parts.append(f"- Place ID: {rc_data['placeId']}")
        if rc_data.get("keyword"):
            parts.append(f"- Keyword cercata: \"{rc_data['keyword']}\"")
        ranking = rc_data.get("ranking", {})
        if ranking.get("mainRank"):
            parts.append(f"- Posizione trovata: {ranking['mainRank']}°")
        if ranking.get("competitorsAhead"):
            parts.append(f"- Competitor davanti: {ranking['competitorsAhead']}")
        if ranking.get("estimatedLostCustomers"):
            parts.append(f"- Clienti persi/settimana stimati: ~{ranking['estimatedLostCustomers']}")
        if rc_data.get("dailyCovers"):
            parts.append(f"- Coperti/giorno dichiarati: {rc_data['dailyCovers']}")
        if rc_data.get("estimatedMonthlyReviews"):
            parts.append(f"- Stima recensioni mensili con MenuChat: ~{rc_data['estimatedMonthlyReviews']}")
        if rc_data.get("hasDigitalMenu") is not None:
            parts.append(f"- Ha menu digitale: {'si' if rc_data['hasDigitalMenu'] else 'no'}")

        full = ranking.get("fullResults", {})
        comps = full.get("competitors", [])
        if comps:
            parts.append("- Competitor trovati nel rank check:")
            for c in comps[:5]:
                parts.append(f"  * {c.get('name')}: pos {c.get('rank')}, {c.get('rating')} stelle, {c.get('reviews')} rec, place_id: {c.get('place_id')}")

        main_coords = full.get("mainResult", {}).get("coordinates", {})
        if main_coords.get("lat") and main_coords.get("lng"):
            parts.append(f"- Coordinate dal rank check: lat={main_coords['lat']}, lng={main_coords['lng']}")

    smartlead = getattr(request, "smartlead_data", None)
    if smartlead and getattr(smartlead, "campaign_id", None):
        parts.append(f"\nSMARTLEAD: campaignId={smartlead.campaign_id}, leadId={smartlead.lead_id}")

    messages = getattr(request, "messages", []) or []
    if messages:
        parts.append(f"\nSTORICO CONVERSAZIONE ({len(messages)} messaggi):")
        recent = messages[-6:] if len(messages) > 6 else messages
        for m in recent:
            role = m.role if hasattr(m, "role") else m.get("role", "?")
            content = m.content if hasattr(m, "content") else m.get("content", "")
            parts.append(f"[{role.upper()}]: {content[:300]}")

    if contact.get("status"):
        parts.append(f"- Stato CRM: {contact['status']}")
    if contact.get("notes"):
        parts.append(f"- Note CRM: {contact['notes']}")
    if contact.get("callback_at"):
        parts.append(f"- Callback programmato: {contact['callback_at']}")
        if contact.get("callback_note"):
            parts.append(f"  Nota callback: {contact['callback_note']}")

    enrichment = getattr(request, "crm_enrichment", None)
    if enrichment:
        if enrichment.conversation_summary:
            parts.append(f"\nRIASSUNTO CONVERSAZIONE PRECEDENTE:\n{enrichment.conversation_summary}")

        if enrichment.contact_notes:
            parts.append(f"\nNOTE SUL CONTATTO:\n{enrichment.contact_notes}")

        if enrichment.human_notes:
            parts.append(f"\nNOTE DEL TEAM VENDITE ({len(enrichment.human_notes)}):")
            for n in enrichment.human_notes:
                date = n.get("date", n.get("at", ""))
                if date:
                    date = str(date)[:10]
                parts.append(f"  [{date}] {n.get('note', '')}")

        if enrichment.call_history:
            parts.append(f"\nSTORICO CHIAMATE ({len(enrichment.call_history)} chiamate):")
            for call in enrichment.call_history:
                date = str(call.date)[:10] if call.date else "N/A"
                dur = call.duration_seconds
                dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else "0:00"
                line = f"  [{date}] {dur_str} | esito: {call.outcome or 'N/A'}"
                if call.initiated_by:
                    line += f" | da: {call.initiated_by}"
                parts.append(line)
                if call.notes:
                    parts.append(f"    📝 {call.notes}")
                if call.transcript:
                    parts.append(f"    🎙️ TRASCRIZIONE:\n{_indent(call.transcript, 6)}")

        if enrichment.activity_summary:
            s = enrichment.activity_summary
            parts.append(f"\nATTIVITÀ CRM: {s.get('total_activities', 0)} totali")
            if s.get("calls_made"):
                parts.append(f"  Chiamate: {s['calls_made']} (risposte: {s.get('calls_answered', '?')})")
            if s.get("last_call_date"):
                parts.append(f"  Ultima chiamata: {str(s['last_call_date'])[:10]} → {s.get('last_call_outcome', 'N/A')}")
            if s.get("status_changes"):
                parts.append(f"  Cambi stato: {' → '.join(s['status_changes'])}")

    objs = getattr(request, "existing_objections", []) or []
    if objs:
        parts.append(f"\nOBIEZIONI GIÀ EMERSE: {', '.join(objs)}")
    pps = getattr(request, "existing_pain_points", []) or []
    if pps:
        parts.append(f"PAIN POINTS RILEVATI: {', '.join(pps)}")

    days = getattr(request, "days_since_last_contact", None)
    if days:
        parts.append(f"\nGIORNI DALL'ULTIMO CONTATTO: {days}")

    stage = getattr(request, "stage", "initial_reply")
    lead_source = getattr(request, "lead_source", "smartlead_outbound")
    is_first = getattr(request, "is_first_contact", False)
    parts.append(f"\nFASE: {stage} | FONTE: {lead_source} | PRIMO CONTATTO: {'sì' if is_first else 'no'}")

    return "\n".join(parts)


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.split("\n"))


def _extract_contact(request) -> dict:
    c = request.contact
    return {
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "city": c.city,
        "address": c.address,
        "rating": c.rating,
        "reviews": c.reviews,
        "source": c.source,
        "category": c.category,
        "website": c.website,
        "google_maps_link": c.google_maps_link,
        "contact_person": c.contact_person,
        "status": c.status,
        "place_id": c.place_id,
        "coordinates": c.coordinates,
        "call_requested": c.call_requested,
        "call_preference": c.call_preference,
        "notes": c.notes,
        "callback_at": c.callback_at,
        "callback_note": c.callback_note,
    }


async def researcher_node(state: AgentState) -> dict:
    request = state["request"]
    contact = _extract_contact(request)
    rc_data = getattr(request, "rank_checker_data", None) or {}

    user_message = _build_user_context(request, contact, rc_data)
    messages: list[dict] = [{"role": "user", "content": user_message}]

    settings = get_settings()
    client = _get_client()

    all_results: dict[str, list] = {}
    done_result: dict | None = None
    total_input_tokens = state.get("total_input_tokens", 0)
    total_output_tokens = state.get("total_output_tokens", 0)

    for round_num in range(MAX_ROUNDS):
        logger.info("Researcher round %d", round_num + 1)

        resp = await client.messages.create(
            model=settings.model_writer,
            max_tokens=4000,
            system=RESEARCHER_SYSTEM_PROMPT,
            tools=RESEARCHER_TOOLS,
            messages=messages,
        )

        total_input_tokens += resp.usage.input_tokens or 0
        total_output_tokens += resp.usage.output_tokens or 0

        if resp.stop_reason == "tool_use":
            tool_results_content = []

            for block in resp.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    logger.info("Researcher calls: %s(%s)", tool_name, json.dumps(tool_input, ensure_ascii=False)[:200])

                    result = await _execute_tool(tool_name, tool_input)

                    if tool_name == "done":
                        done_result = result
                    else:
                        if tool_name not in all_results:
                            all_results[tool_name] = []
                        all_results[tool_name].append(result)

                    result_str = json.dumps(result, ensure_ascii=False, default=str)
                    if len(result_str) > 3000:
                        result_str = result_str[:3000] + "...(truncated)"

                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results_content})

            if done_result:
                logger.info("Researcher done after %d rounds", round_num + 1)
                break
        else:
            logger.info("Researcher ended without calling done (round %d)", round_num + 1)
            break

    crm_context = _build_crm_context(request)
    research = _assemble_research(all_results, done_result, contact, rc_data, crm_context)

    logger.info(
        "Research complete: tools_called=%s rounds=%d",
        list(all_results.keys()),
        round_num + 1 if 'round_num' in dir() else 0,
    )

    return {
        "research": research,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
    }


def _build_crm_context(request) -> str | None:
    """Build a text summary of CRM enrichment data to pass through the graph."""
    enrichment = getattr(request, "crm_enrichment", None)
    if not enrichment:
        return None

    parts = []
    task_type = getattr(request, "task_type", "")
    days = getattr(request, "days_since_last_contact", None)

    if task_type:
        parts.append(f"TIPO AZIONE: {task_type}")
    if days:
        parts.append(f"GIORNI DALL'ULTIMO CONTATTO: {days}")

    contact = getattr(request, "contact", None)
    if contact:
        if contact.status:
            parts.append(f"STATO CRM: {contact.status}")
        if contact.callback_note:
            parts.append(f"CALLBACK: {contact.callback_note}")
        if contact.notes:
            parts.append(f"NOTE CONTATTO: {contact.notes}")

    if enrichment.conversation_summary:
        parts.append(f"\nRIASSUNTO CONVERSAZIONE:\n{enrichment.conversation_summary}")

    if enrichment.human_notes:
        parts.append(f"\nNOTE TEAM VENDITE:")
        for n in enrichment.human_notes:
            date = str(n.get("date", ""))[:10]
            parts.append(f"  [{date}] {n.get('note', '')}")

    if enrichment.call_history:
        parts.append(f"\nSTORICO CHIAMATE ({len(enrichment.call_history)}):")
        for call in enrichment.call_history:
            date = str(call.date)[:10] if call.date else "N/A"
            dur = call.duration_seconds
            dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else "0:00"
            line = f"  [{date}] {dur_str} | esito: {call.outcome or 'N/A'}"
            parts.append(line)
            if call.notes:
                parts.append(f"    📝 {call.notes}")
            if call.transcript:
                parts.append(f"    🎙️ TRASCRIZIONE:\n{_indent(call.transcript, 6)}")

    if enrichment.contact_notes:
        parts.append(f"\nNOTE CRM: {enrichment.contact_notes}")

    if enrichment.activity_summary:
        s = enrichment.activity_summary
        parts.append(f"\nATTIVITÀ: {s.get('total_activities', 0)} totali, {s.get('calls_made', 0)} chiamate ({s.get('calls_answered', '?')} risposte)")
        if s.get("status_changes"):
            parts.append(f"  Cambi stato: {' → '.join(s['status_changes'])}")

    msgs = getattr(request, "messages", []) or []
    if msgs:
        parts.append(f"\nSTORICO MESSAGGI ({len(msgs)}):")
        for m in msgs[-6:]:
            role = m.role if hasattr(m, "role") else m.get("role", "?")
            content = m.content if hasattr(m, "content") else m.get("content", "")
            parts.append(f"  [{role.upper()}]: {content[:200]}")

    prev = getattr(request, "previous_insights", None)
    if prev:
        if prev.get("objections"):
            parts.append(f"\nOBIEZIONI PRECEDENTI: {', '.join(prev['objections'])}")
        if prev.get("pain_points"):
            parts.append(f"PAIN POINTS PRECEDENTI: {', '.join(prev['pain_points'])}")

    return "\n".join(parts) if parts else None


def _assemble_research(
    all_results: dict[str, list],
    done_result: dict | None,
    contact: dict,
    rc_data: dict,
    crm_context: str | None = None,
) -> ResearchData:
    """Assemble a ResearchData from all accumulated tool results."""

    google_data = None
    for r in all_results.get("research_business", []):
        if r and not r.get("error"):
            google_data = r
            if not contact.get("rating") and r.get("rating"):
                contact["rating"] = r["rating"]
            if not contact.get("reviews") and r.get("reviews"):
                contact["reviews"] = r["reviews"]

    all_reviews = []
    for r in all_results.get("fetch_reviews", []):
        all_reviews.extend(r.get("reviews", []))

    negative_reviews = [r for r in all_reviews if (r.get("rating") or 5) <= 3]
    neg_summary = None
    if negative_reviews:
        neg_texts = [f"★{r['rating']}: {r['text'][:150]}" for r in negative_reviews[:5]]
        neg_summary = f"{len(negative_reviews)} recensioni negative trovate:\n" + "\n".join(neg_texts)

    similar_clients = []
    fallback_studies = []
    for r in all_results.get("search_similar_clients", []):
        similar_clients.extend(r.get("clients", []))
        fallback_studies.extend(r.get("fallback_case_studies", []))

    email_thread = []
    for r in all_results.get("fetch_email_thread", []):
        if isinstance(r, list):
            email_thread.extend(r)

    ranking_data = None
    competitors = []
    for r in all_results.get("check_ranking", []):
        if r and not r.get("error"):
            ranking_data = r

    if not ranking_data and rc_data:
        ranking_raw = rc_data.get("ranking", {})
        if ranking_raw.get("mainRank"):
            ranking_data = {
                "keyword": rc_data.get("keyword"),
                "user_rank": ranking_raw.get("mainRank"),
                "estimated_lost_customers_per_week": ranking_raw.get("estimatedLostCustomers"),
            }
        raw_comps = ranking_raw.get("fullResults", {}).get("competitors", [])
        competitors = [
            {"name": c.get("name"), "rank": c.get("rank"), "rating": c.get("rating"), "reviews": c.get("reviews")}
            for c in raw_comps[:5]
        ]

    if ranking_data and not competitors:
        competitors = ranking_data.get("competitors_ahead", [])

    ranking = None
    if ranking_data:
        ranking = {
            "keyword": ranking_data.get("keyword", rc_data.get("keyword")),
            "main_rank": ranking_data.get("user_rank"),
            "competitors_ahead": len(ranking_data.get("competitors_ahead", [])) if isinstance(ranking_data.get("competitors_ahead"), list) else ranking_data.get("competitors_ahead"),
            "estimated_lost_customers": ranking_data.get("estimated_lost_customers_per_week"),
            "daily_covers": rc_data.get("dailyCovers"),
        }

    daily_covers = rc_data.get("dailyCovers", 0) or 0
    proj_2w = round(daily_covers * 14 * 0.06) if daily_covers > 0 else None
    proj_12m = round(daily_covers * 365 * 0.06) if daily_covers > 0 else None

    competitor_gap = None
    if ranking and ranking.get("main_rank") and competitors:
        top = competitors[0] if competitors else None
        if top:
            competitor_gap = (
                f"Posizione {ranking['main_rank']}° per '{ranking['keyword']}'. "
                f"Davanti: {top.get('name')} (pos {top.get('rank')}, {top.get('reviews', '?')} recensioni)."
            )

    data_summary = _build_data_summary(contact, ranking, competitors, similar_clients, fallback_studies, all_reviews, done_result)

    return ResearchData(
        contact=contact,
        ranking=ranking,
        competitors=competitors,
        google_data=google_data,
        recent_reviews=all_reviews,
        negative_reviews_summary=neg_summary,
        similar_clients=similar_clients,
        fallback_case_studies=fallback_studies,
        email_thread=email_thread,
        competitor_gap=competitor_gap,
        projected_reviews_2_weeks=proj_2w,
        projected_reviews_12_months=proj_12m,
        has_digital_menu=rc_data.get("hasDigitalMenu"),
        available_data_summary=data_summary,
        crm_context=crm_context,
    )


def _build_data_summary(contact, ranking, competitors, similar_clients, fallback_studies, all_reviews, done_result) -> str:
    """Summary for the reviewer's anti-hallucination check + strategist context."""
    parts = [f"Nome: {contact.get('name', 'N/A')}"]
    if contact.get("phone"):
        parts.append(f"Telefono: {contact['phone']}")
    if contact.get("rating"):
        parts.append(f"Rating Google: {contact['rating']}")
    if contact.get("reviews"):
        parts.append(f"Recensioni Google totali: {contact['reviews']}")
    if ranking and ranking.get("main_rank"):
        parts.append(f"Posizione Maps: {ranking['main_rank']}° per \"{ranking.get('keyword')}\"")
    if ranking and ranking.get("estimated_lost_customers"):
        parts.append(f"Clienti persi/settimana stimati: ~{ranking['estimated_lost_customers']}")
    if ranking and ranking.get("daily_covers"):
        parts.append(f"Coperti/giorno: {ranking['daily_covers']}")
    for c in competitors[:5]:
        parts.append(f"Competitor: {c.get('name')} (pos {c.get('rank')}, rating {c.get('rating', '?')}, {c.get('reviews', '?')} rec)")
    for c in similar_clients[:3]:
        parts.append(
            f"Cliente MenuChat REALE: {c.get('name')} ({c.get('city')}) — "
            f"raccolte {c.get('reviews_gained')} recensioni CON MENUCHAT in {c.get('months_active')} mesi "
            f"(media {c.get('avg_reviews_per_month', '?')}/mese). "
            f"Erano a {c.get('initial_reviews', '?')}, ora {c.get('current_reviews', '?')}. Rating {c.get('rating', '?')}/5."
        )
        if c.get("menu_url"):
            parts.append(f"  → Menu: {c['menu_url']}")
    for c in fallback_studies[:3]:
        parts.append(f"Case study: {c['name']} ({c['city']}) — {c['result']}")
    if all_reviews:
        neg = [r for r in all_reviews if (r.get("rating") or 5) <= 3]
        if neg:
            parts.append(f"Recensioni negative trovate: {len(neg)}")
            for r in neg[:3]:
                parts.append(f"  ★{r['rating']}: {r['text'][:100]}")

    if done_result and done_result.get("key_findings"):
        parts.append("\nRICERCATORE — DATI CHIAVE:")
        for f in done_result["key_findings"]:
            parts.append(f"  • {f}")

    return "\n".join(parts)
