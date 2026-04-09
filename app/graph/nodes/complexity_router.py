"""
Complexity Router — System 1 vs System 2 decision.
Uses Haiku for ultra-fast classification.
Simple cases skip research; complex cases get the full pipeline.
"""

import json
import logging

import anthropic

from app.config import get_settings
from app.graph.state import AgentState

logger = logging.getLogger("agent-service.nodes.router")

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


ROUTER_PROMPT = """Classify this lead message in two dimensions:

1. COMPLEXITY:
SIMPLE (no deep research needed):
- Lead gave a phone number → handoff
- Lead proposed a specific time/date → scheduling
- Autoresponder / out of office / booking system
- Email changed (new email provided)
- Very short response with no substance ("ok", "grazie")
- Business closed / not operational anymore

COMPLEX (needs deep research + strategic reasoning):
- Lead asks questions about the service
- Lead asks about price, how it works, legality
- Lead raises objections (already have a provider, no budget, no time, wrong data)
- Lead wants more info, a presentation, or materials
- Lead is curious but hesitant
- Lead says to come back later / seasonal closure
- Lead challenges data accuracy
- First contact with a rank checker lead (outreach)
- Any response that requires understanding the lead's situation

2. SENTIMENT of the lead:
- positive: enthusiastic, interested, friendly
- neutral: informational, factual, no emotion
- annoyed: slightly irritated, impatient, bothered
- angry: upset, hostile, complaining, threatening
- sad: disappointed, discouraged, closing business

Respond with ONLY a JSON: {"complexity": "simple" | "complex", "sentiment": "positive" | "neutral" | "annoyed" | "angry" | "sad", "reason": "brief reason"}"""


async def complexity_router_node(state: AgentState) -> dict:
    request = state["request"]
    lead_message = getattr(request, "lead_message", "") or ""
    classification = getattr(request, "classification", None)
    is_first_contact = getattr(request, "is_first_contact", False)

    if is_first_contact:
        return {"complexity": "complex", "lead_sentiment": "neutral"}

    if classification:
        cat = classification.category if hasattr(classification, "category") else classification.get("category", "")
        conf = classification.confidence if hasattr(classification, "confidence") else classification.get("confidence", 0)
        extracted = classification.extracted if hasattr(classification, "extracted") else classification.get("extracted", {})

        if cat == "OUT_OF_OFFICE":
            return {"complexity": "simple", "lead_sentiment": "neutral"}
        if cat == "DO_NOT_CONTACT":
            return {"complexity": "simple", "lead_sentiment": "angry"}
        if cat == "INTERESTED" and conf >= 0.9 and extracted.get("phone"):
            return {"complexity": "simple", "lead_sentiment": "positive"}

    if not lead_message or len(lead_message.strip()) < 15:
        return {"complexity": "simple", "lead_sentiment": "neutral"}

    try:
        settings = get_settings()
        client = _get_client()
        resp = await client.messages.create(
            model=settings.model_router,
            max_tokens=150,
            temperature=0,
            messages=[{"role": "user", "content": f"{ROUTER_PROMPT}\n\nLead message: \"{lead_message}\""}],
        )
        text = resp.content[0].text.strip()
        parsed = json.loads(text[text.index("{"):text.rindex("}") + 1])
        complexity = parsed.get("complexity", "complex")
        sentiment = parsed.get("sentiment", "neutral")
        logger.info("Router decision: complexity=%s sentiment=%s — %s", complexity, sentiment, parsed.get("reason", ""))
        return {
            "complexity": complexity,
            "lead_sentiment": sentiment,
            "total_input_tokens": state.get("total_input_tokens", 0) + (resp.usage.input_tokens or 0),
            "total_output_tokens": state.get("total_output_tokens", 0) + (resp.usage.output_tokens or 0),
        }
    except Exception as e:
        logger.warning("Router fallback to complex: %s", e)
        return {"complexity": "complex", "lead_sentiment": "neutral"}
