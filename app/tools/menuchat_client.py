"""
MenuChat backend API client.
Fetches similar restaurants (social proof) and restaurant search data.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("agent-service.tools.menuchat")


async def search_similar_clients(
    cuisine_type: str, *, city: str | None = None, region: str | None = None
) -> dict[str, Any]:
    """
    Find MenuChat restaurants similar to the lead for social proof.
    Internally does progressive fallback: type+city → city only → type only → no filter.
    """
    settings = get_settings()
    if not settings.menuchat_backend_url:
        return {"clients": [], "note": "MenuChat backend not configured"}

    searches = []
    if cuisine_type and city:
        searches.append({"type": cuisine_type, "city": city})
    if city:
        searches.append({"city": city})
    if cuisine_type:
        searches.append({"type": cuisine_type})
    searches.append({})

    for search_params in searches:
        result = await _do_search(settings, search_params)
        if result.get("clients"):
            return result

    return {
        "clients": [],
        "note": "Nessun cliente MenuChat trovato in nessuna ricerca.",
    }


async def _do_search(settings, extra_params: dict) -> dict[str, Any]:
    params: dict[str, str] = {"limit": "3"}
    params.update(extra_params)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.menuchat_backend_url}/api/restaurants/similar",
                params=params,
                headers={"x-api-key": settings.crm_api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        restaurants = data.get("restaurants", [])
        if restaurants:
            return {
                "clients": [
                    {
                        "name": r.get("name"),
                        "city": _extract_city(r.get("address", {})),
                        "full_address": r.get("address", {}).get("formattedAddress", ""),
                        "current_reviews": r.get("currentReviewCount") or r.get("googleRating", {}).get("reviewCount"),
                        "initial_reviews": r.get("initialReviewCount", 0),
                        "reviews_gained": r.get("reviewsGained"),
                        "months_active": r.get("monthsActive"),
                        "avg_reviews_per_month": r.get("avgReviewsPerMonth"),
                        "rating": r.get("googleRating", {}).get("rating"),
                        "menu_url": r.get("menuUrl") or f"https://menuchat.it/menu/{r.get('_id')}",
                        "menu_item_count": r.get("menuItemCount", 0),
                        "has_completed_menu": r.get("hasCompletedMenu", False),
                    }
                    for r in restaurants
                ],
            }
        return {"clients": []}
    except Exception as e:
        logger.warning("search_similar_clients failed (%s): %s", extra_params, e)
        return {"clients": [], "error": str(e)}


def _extract_city(address: dict) -> str:
    """Extract city name from formattedAddress like 'Via X, 00127 Roma RM, Italy'."""
    formatted = address.get("formattedAddress", "")
    if not formatted:
        return ""
    parts = formatted.split(",")
    if len(parts) >= 3:
        city_part = parts[-2].strip()
        tokens = city_part.split()
        city_tokens = [t for t in tokens if not t.isdigit() and len(t) > 2]
        return " ".join(city_tokens) if city_tokens else city_part
    return ""
