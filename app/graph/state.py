"""
LangGraph AgentState — the typed state object that flows through the graph.
Every node reads from and writes to this state.
"""

from __future__ import annotations

from typing import Any, TypedDict

from app.api.models import AgentRequest, AgentResponse, ProactiveRequest


class ResearchData(TypedDict, total=False):
    contact: dict
    ranking: dict | None
    competitors: list[dict]
    google_data: dict | None
    recent_reviews: list[dict]
    negative_reviews_summary: str | None
    similar_clients: list[dict]
    fallback_case_studies: list[dict]
    email_thread: list[dict]
    sequence_number: int | None
    competitor_gap: str | None
    projected_reviews_2_weeks: int | None
    projected_reviews_12_months: int | None
    has_digital_menu: bool | None
    available_data_summary: str
    crm_context: str | None


class AgentState(TypedDict, total=False):
    # Input — set once at entry, never mutated
    request: AgentRequest | ProactiveRequest
    request_type: str  # "reactive" | "proactive" | "resume"
    thread_id: str

    # Wake context (for resumed workflows)
    wake_context: dict

    # Complexity routing
    complexity: str  # "simple" | "complex"

    # Research
    research: ResearchData

    # Strategy
    strategy: dict | None
    strategy_approved: bool
    strategy_feedback: str | None
    strategy_attempts: int

    # Generation
    draft: str | None
    whatsapp_draft: str | None
    review_result: dict | None
    review_attempts: int

    # Memory
    episodic_examples: list[dict]
    contact_memories: list[dict]

    # Tool intents accumulated during the run
    tool_intents: list[dict]

    # Final response
    response: AgentResponse | None

    # Token / cost tracking
    total_input_tokens: int
    total_output_tokens: int
