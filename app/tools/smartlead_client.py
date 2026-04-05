"""
Smartlead API client.
Fetches email thread history, updates lead email, pauses/resumes leads.
"""

import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("agent-service.tools.smartlead")

BASE_URL = "https://server.smartlead.ai/api/v1"


def _strip_html(html: str) -> str:
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def fetch_message_history(campaign_id: str, lead_id: str) -> list[dict[str, Any]]:
    """Fetch complete email thread from Smartlead."""
    settings = get_settings()
    if not settings.smartlead_api_key:
        return []

    url = f"{BASE_URL}/campaigns/{campaign_id}/leads/{lead_id}/message-history"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"api_key": settings.smartlead_api_key})
            resp.raise_for_status()
            history = resp.json()

        if not isinstance(history, list):
            return []

        return [
            {
                "type": "SENT" if msg.get("type") == "SENT" else "LEAD",
                "subject": msg.get("subject", ""),
                "body": _strip_html(msg.get("email_body", ""))[:600],
                "date": msg.get("time"),
            }
            for msg in history[-8:]
        ]
    except Exception as e:
        logger.warning("fetch_message_history failed: %s", e)
        return []


async def update_lead_email(campaign_id: str, lead_id: str, new_email: str) -> dict:
    """Update lead's email address in Smartlead."""
    settings = get_settings()
    if not settings.smartlead_api_key:
        return {"success": False, "error": "Smartlead API key not configured"}

    url = f"{BASE_URL}/campaigns/{campaign_id}/leads/{lead_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                params={"api_key": settings.smartlead_api_key},
                json={"email": new_email},
            )
            resp.raise_for_status()
        return {"success": True, "new_email": new_email}
    except Exception as e:
        logger.warning("update_lead_email failed: %s", e)
        return {"success": False, "error": str(e)}


async def fetch_lead_by_email(email: str) -> dict | None:
    """Fetch lead data by email address."""
    settings = get_settings()
    if not settings.smartlead_api_key:
        return None

    url = f"{BASE_URL}/leads/"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url, params={"api_key": settings.smartlead_api_key, "email": email}
            )
            resp.raise_for_status()
            data = resp.json()
        return data if data else None
    except Exception as e:
        logger.warning("fetch_lead_by_email failed: %s", e)
        return None
