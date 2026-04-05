"""
SerpAPI client — Google Maps business data, reviews, ranking, competitor research.
Tools used by the agentic researcher.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("agent-service.tools.serpapi")

SERPAPI_BASE = "https://serpapi.com/search.json"


def _get_key() -> str:
    return get_settings().serpapi_key


async def research_business(
    *, place_id: str | None = None, business_name: str | None = None, city: str | None = None
) -> dict[str, Any]:
    """Fetch business details from Google Maps via SerpAPI."""
    key = _get_key()
    if not key:
        return {"error": "SERPAPI_KEY not configured"}

    params: dict[str, Any] = {"engine": "google_maps", "api_key": key, "hl": "it"}

    if place_id:
        params["place_id"] = place_id
    elif business_name:
        params["type"] = "search"
        params["q"] = f"{business_name} {city}" if city else business_name
    else:
        return {"error": "Need place_id or business_name"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("place_results"):
        p = data["place_results"]
        return {
            "name": p.get("title"),
            "rating": p.get("rating"),
            "reviews": p.get("reviews"),
            "address": p.get("address"),
            "phone": p.get("phone"),
            "website": p.get("website"),
            "type": p.get("type", ""),
            "hours": p.get("hours"),
            "place_id": p.get("place_id"),
            "reviews_breakdown": p.get("reviews_per_score", {}),
        }

    if data.get("local_results"):
        first = data["local_results"][0]
        return {
            "name": first.get("title"),
            "rating": first.get("rating"),
            "reviews": first.get("reviews"),
            "address": first.get("address"),
            "phone": first.get("phone"),
            "type": first.get("type"),
            "place_id": first.get("place_id"),
            "position": first.get("position"),
        }

    return {"error": "No results found"}


async def fetch_reviews(place_id: str, *, next_page_token: str | None = None) -> dict:
    """
    Fetch Google reviews for a place. Returns up to 8 reviews per call.
    Pass next_page_token to paginate and get more reviews.
    """
    key = _get_key()
    if not key:
        return {"reviews": [], "error": "SERPAPI_KEY not configured"}

    params: dict[str, Any] = {
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "api_key": key,
        "hl": "it",
        "sort_by": "newestFirst",
    }
    if next_page_token:
        params["next_page_token"] = next_page_token

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(SERPAPI_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

        reviews = []
        for r in data.get("reviews", []):
            reviews.append({
                "rating": r.get("rating"),
                "text": (r.get("snippet") or r.get("text") or "")[:500],
                "date": r.get("date") or r.get("iso_date"),
                "author": r.get("user", {}).get("name", ""),
            })

        return {
            "reviews": reviews,
            "next_page_token": data.get("serpapi_pagination", {}).get("next_page_token"),
        }
    except Exception as e:
        logger.warning("fetch_reviews failed for %s: %s", place_id, e)
        return {"reviews": [], "error": str(e)}


async def check_ranking(
    keyword: str,
    *,
    latitude: float,
    longitude: float,
    place_id: str | None = None,
    restaurant_name: str | None = None,
) -> dict:
    """
    Live rank check on Google Maps for a keyword + location.
    Finds the restaurant's position and identifies competitors.
    Matches by place_id first, then by name.
    """
    key = _get_key()
    if not key:
        return {"error": "SERPAPI_KEY not configured"}

    params: dict[str, Any] = {
        "engine": "google_maps",
        "type": "search",
        "q": keyword,
        "ll": f"@{latitude},{longitude},15z",
        "api_key": key,
        "hl": "it",
        "num": "20",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("local_results", [])
    user_rank = None
    user_data = None
    competitors_ahead = []
    all_competitors = []

    for r in results:
        is_match = False
        if place_id and r.get("place_id") == place_id:
            is_match = True
        elif restaurant_name:
            r_name = (r.get("title") or "").lower()
            s_name = restaurant_name.lower()
            if r_name in s_name or s_name in r_name:
                is_match = True

        if is_match:
            user_rank = r.get("position")
            user_data = {
                "name": r.get("title"),
                "rank": user_rank,
                "rating": r.get("rating"),
                "reviews": r.get("reviews"),
                "place_id": r.get("place_id"),
            }
        else:
            comp = {
                "name": r.get("title"),
                "rank": r.get("position"),
                "rating": r.get("rating"),
                "reviews": r.get("reviews"),
                "place_id": r.get("place_id"),
            }
            all_competitors.append(comp)
            if user_rank is None or (r.get("position") or 99) < user_rank:
                competitors_ahead.append(comp)

    estimated_lost = None
    if user_rank and user_rank > 1:
        estimated_lost = round((user_rank - 1) * 5)

    return {
        "keyword": keyword,
        "user_rank": user_rank or "Fuori dalla Top 20",
        "user_restaurant": user_data,
        "competitors_ahead": competitors_ahead[:5],
        "all_results": all_competitors[:10],
        "total_results": len(results),
        "estimated_lost_customers_per_week": estimated_lost,
    }


async def research_competitor(
    *, place_id: str | None = None, competitor_name: str | None = None, city: str | None = None
) -> dict[str, Any]:
    """Look up a specific competitor on Google Maps."""
    return await research_business(place_id=place_id, business_name=competitor_name, city=city)
