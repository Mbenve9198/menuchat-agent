"""
Deep Researcher node — deterministic (no LLM), parallel API calls.
Gathers all data the strategist needs to reason.
"""

import asyncio
import logging
from typing import Any

from app.graph.state import AgentState, ResearchData
from app.tools.serpapi_client import research_business, fetch_recent_reviews
from app.tools.menuchat_client import search_similar_clients
from app.tools.smartlead_client import fetch_message_history

logger = logging.getLogger("agent-service.nodes.researcher")


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
    }


async def researcher_node(state: AgentState) -> dict:
    request = state["request"]
    contact = _extract_contact(request)
    rc_data = getattr(request, "rank_checker_data", None) or {}
    smartlead = getattr(request, "smartlead_data", None)

    ranking = None
    competitors: list[dict] = []
    if rc_data:
        ranking_raw = rc_data.get("ranking", {})
        ranking = {
            "keyword": rc_data.get("keyword"),
            "main_rank": ranking_raw.get("mainRank"),
            "competitors_ahead": ranking_raw.get("competitorsAhead"),
            "estimated_lost_customers": ranking_raw.get("estimatedLostCustomers"),
            "daily_covers": rc_data.get("dailyCovers"),
        }
        raw_comps = ranking_raw.get("fullResults", {}).get("competitors", [])
        competitors = [
            {"name": c.get("name"), "rank": c.get("rank"), "rating": c.get("rating"), "reviews": c.get("reviews")}
            for c in raw_comps[:5]
        ]

    # Parallel API calls
    tasks: dict[str, Any] = {}

    needs_google = not contact.get("rating") or not contact.get("reviews")
    if needs_google and (contact.get("name") and contact.get("city")):
        tasks["google"] = research_business(business_name=contact["name"], city=contact["city"])

    cuisine = contact.get("category") or "ristorante"
    city = contact.get("city")
    tasks["similar"] = _search_similar_progressive(cuisine, city)

    campaign_id = smartlead.campaign_id if smartlead else None
    lead_id = smartlead.lead_id if smartlead else None
    if campaign_id and lead_id:
        tasks["email_thread"] = fetch_message_history(campaign_id, lead_id)

    results = await _gather_dict(tasks)

    google_data = results.get("google")
    if google_data and not google_data.get("error"):
        if not contact.get("rating") and google_data.get("rating"):
            contact["rating"] = google_data["rating"]
        if not contact.get("reviews") and google_data.get("reviews"):
            contact["reviews"] = google_data["reviews"]
    else:
        google_data = None

    similar_result = results.get("similar", {})
    similar_clients = similar_result.get("clients", [])
    fallback_studies = similar_result.get("fallback_case_studies", [])

    email_thread = results.get("email_thread", [])

    # Fetch recent reviews if we have a place_id
    recent_reviews: list[dict] = []
    place_id = (google_data or {}).get("place_id")
    if place_id:
        recent_reviews = await fetch_recent_reviews(place_id, num_reviews=8)

    # Derived calculations
    negative_reviews = [r for r in recent_reviews if (r.get("rating") or 5) <= 3]
    neg_summary = None
    if negative_reviews:
        neg_texts = [f"★{r['rating']}: {r['text'][:100]}" for r in negative_reviews[:3]]
        neg_summary = f"{len(negative_reviews)} recensioni negative recenti:\n" + "\n".join(neg_texts)

    daily_covers = ranking.get("daily_covers", 0) if ranking else 0
    proj_2w = round(daily_covers * 14 * 0.06) if daily_covers > 0 else None
    proj_12m = round(daily_covers * 365 * 0.06) if daily_covers > 0 else None

    competitor_gap = None
    if ranking and ranking.get("main_rank") and competitors:
        top_comp = competitors[0] if competitors else None
        if top_comp:
            competitor_gap = (
                f"Posizione {ranking['main_rank']}° per '{ranking['keyword']}'. "
                f"Davanti: {top_comp['name']} (pos {top_comp['rank']}, {top_comp.get('reviews', '?')} recensioni)."
            )

    data_summary = _build_data_summary(contact, ranking, competitors, similar_clients, fallback_studies)

    research: ResearchData = {
        "contact": contact,
        "ranking": ranking,
        "competitors": competitors,
        "google_data": google_data,
        "recent_reviews": recent_reviews,
        "negative_reviews_summary": neg_summary,
        "similar_clients": similar_clients,
        "fallback_case_studies": fallback_studies,
        "email_thread": email_thread,
        "sequence_number": None,
        "competitor_gap": competitor_gap,
        "projected_reviews_2_weeks": proj_2w,
        "projected_reviews_12_months": proj_12m,
        "has_digital_menu": rc_data.get("hasDigitalMenu"),
        "available_data_summary": data_summary,
    }

    logger.info(
        "Research complete: google=%s reviews=%d similar=%d thread=%d neg=%d",
        bool(google_data), len(recent_reviews), len(similar_clients), len(email_thread), len(negative_reviews),
    )

    return {"research": research}


async def _search_similar_progressive(cuisine: str, city: str | None) -> dict:
    """Progressive search: city → region → national."""
    result = await search_similar_clients(cuisine, city=city)
    if result.get("clients"):
        return result
    if city:
        result = await search_similar_clients(cuisine, region=city)
        if result.get("clients"):
            return result
    result = await search_similar_clients(cuisine)
    return result


async def _gather_dict(tasks: dict[str, Any]) -> dict:
    """Run coroutines in parallel, return results keyed by name."""
    if not tasks:
        return {}
    keys = list(tasks.keys())
    coros = [tasks[k] for k in keys]
    results = await asyncio.gather(*coros, return_exceptions=True)
    out = {}
    for k, r in zip(keys, results):
        if isinstance(r, Exception):
            logger.warning("Research task %s failed: %s", k, r)
            out[k] = None
        else:
            out[k] = r
    return out


def _build_data_summary(contact, ranking, competitors, similar_clients, fallback_studies) -> str:
    """Human-readable summary of all available data (for reviewer anti-hallucination check)."""
    parts = [f"Nome: {contact.get('name', 'N/A')}"]
    if contact.get("phone"):
        parts.append(f"Telefono: {contact['phone']}")
    if contact.get("rating"):
        parts.append(f"Rating: {contact['rating']}")
    if contact.get("reviews"):
        parts.append(f"Recensioni: {contact['reviews']}")
    if ranking and ranking.get("main_rank"):
        parts.append(f"Posizione Maps: {ranking['main_rank']}° per \"{ranking.get('keyword')}\"")
    if ranking and ranking.get("estimated_lost_customers"):
        parts.append(f"Clienti persi/settimana: ~{ranking['estimated_lost_customers']}")
    for c in competitors[:3]:
        parts.append(f"Competitor: {c['name']} (pos {c['rank']}, {c.get('reviews', '?')} rec)")
    for c in similar_clients[:3]:
        parts.append(
            f"Cliente MenuChat: {c.get('name')} ({c.get('city')}) — "
            f"{c.get('reviews_gained')} rec in {c.get('months_active')} mesi"
        )
    for c in fallback_studies[:3]:
        parts.append(f"Case study: {c['name']} ({c['city']}) — {c['result']}")
    return "\n".join(parts)
