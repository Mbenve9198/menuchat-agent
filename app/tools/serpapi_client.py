"""
SerpAPI client for Google Maps business data + reviews.
Used by the researcher node for deep research.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("agent-service.tools.serpapi")

SERPAPI_BASE = "https://serpapi.com/search.json"


async def research_business(
    *, place_id: str | None = None, business_name: str | None = None, city: str | None = None
) -> dict[str, Any]:
    """Fetch business details from Google Maps via SerpAPI."""
    settings = get_settings()
    if not settings.serpapi_key:
        return {"error": "SERPAPI_KEY not configured"}

    params: dict[str, Any] = {
        "engine": "google_maps",
        "api_key": settings.serpapi_key,
        "hl": "it",
    }

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


async def fetch_recent_reviews(place_id: str, num_reviews: int = 10) -> list[dict]:
    """Fetch recent Google reviews for a place via SerpAPI."""
    settings = get_settings()
    if not settings.serpapi_key:
        return []

    params = {
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "api_key": settings.serpapi_key,
        "hl": "it",
        "sort_by": "newestFirst",
        "num": str(num_reviews),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(SERPAPI_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

        reviews = []
        for r in data.get("reviews", [])[:num_reviews]:
            reviews.append({
                "rating": r.get("rating"),
                "text": (r.get("snippet") or r.get("text") or "")[:500],
                "date": r.get("date") or r.get("iso_date"),
                "author": r.get("user", {}).get("name", ""),
            })
        return reviews
    except Exception as e:
        logger.warning("fetch_recent_reviews failed for %s: %s", place_id, e)
        return []


async def get_maps_ranking(keyword: str, *, latitude: float | None = None, longitude: float | None = None) -> dict:
    """Check ranking position for a keyword on Google Maps."""
    settings = get_settings()
    if not settings.serpapi_key:
        return {"error": "SERPAPI_KEY not configured"}

    params: dict[str, Any] = {
        "engine": "google_maps",
        "type": "search",
        "q": keyword,
        "api_key": settings.serpapi_key,
        "hl": "it",
        "num": "20",
    }
    if latitude and longitude:
        params["ll"] = f"@{latitude},{longitude},15z"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("local_results", [])
    competitors = []
    for r in results[:10]:
        competitors.append({
            "name": r.get("title"),
            "rank": r.get("position"),
            "rating": r.get("rating"),
            "reviews": r.get("reviews"),
        })

    return {
        "keyword": keyword,
        "total_results": len(results),
        "competitors": competitors,
    }
