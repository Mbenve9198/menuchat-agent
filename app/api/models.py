from __future__ import annotations

from pydantic import BaseModel, Field


# ── Shared sub-models ──────────────────────────────────────────────

class ContactData(BaseModel):
    name: str
    email: str
    phone: str | None = None
    city: str | None = None
    address: str | None = None
    rating: float | None = None
    reviews: int | None = None
    source: str | None = None
    category: str | None = None
    website: str | None = None
    google_maps_link: str | None = None
    contact_person: str | None = None


class Message(BaseModel):
    role: str  # lead | agent | human
    content: str
    channel: str = "email"
    created_at: str | None = None


class Classification(BaseModel):
    category: str  # INTERESTED | NEUTRAL | NOT_INTERESTED | DO_NOT_CONTACT | OUT_OF_OFFICE
    confidence: float = 0.5
    extracted: dict = Field(default_factory=dict)


class SmartleadData(BaseModel):
    campaign_id: str | None = None
    lead_id: str | None = None
    sequence_number: int | None = None


class AgentIdentity(BaseModel):
    name: str = "Marco"
    surname: str = "Benvenuti"
    role: str = "co-founder"


# ── Requests ───────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    """Reactive: lead wrote a message, agent must respond."""
    contact: ContactData
    rank_checker_data: dict | None = None

    conversation_id: str
    messages: list[Message] = Field(default_factory=list)
    stage: str = "initial_reply"
    lead_source: str = "smartlead_outbound"

    lead_message: str
    classification: Classification

    smartlead_data: SmartleadData | None = None

    existing_objections: list[str] = Field(default_factory=list)
    existing_pain_points: list[str] = Field(default_factory=list)
    conversation_summary: str | None = None

    is_first_contact: bool = False
    agent_identity: AgentIdentity = Field(default_factory=AgentIdentity)


class ProactiveRequest(BaseModel):
    """Agent-initiated action: follow-up, outreach, reactivation, break-up."""
    task_type: str
    contact: ContactData
    conversation_id: str | None = None
    messages: list[Message] = Field(default_factory=list)
    lead_source: str = "smartlead_outbound"
    rank_checker_data: dict | None = None
    smartlead_data: SmartleadData | None = None
    agent_identity: AgentIdentity = Field(default_factory=AgentIdentity)

    task_context: dict = Field(default_factory=dict)
    previous_insights: dict | None = None

    days_since_last_contact: int | None = None
    last_outcome: str | None = None


class ResumeRequest(BaseModel):
    """Resume a hibernated workflow from PostgreSQL checkpoint."""
    thread_id: str
    updated_context: dict = Field(default_factory=dict)


# ── Tool Intents (agent -> CRM) ───────────────────────────────────

class ToolIntent(BaseModel):
    tool: str
    params: dict = Field(default_factory=dict)


class Insights(BaseModel):
    objections: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    contact_name: str | None = None
    phone: str | None = None


class StrategyOutput(BaseModel):
    approach: str | None = None
    main_angle: str | None = None
    tone: str | None = None
    reasoning: str | None = None
    raw: dict = Field(default_factory=dict)


# ── Response ───────────────────────────────────────────────────────

class AgentResponse(BaseModel):
    action: str  # draft_ready | schedule_followup | escalate_human | system_action | hibernated
    draft: str | None = None
    channel: str = "email"
    strategy: StrategyOutput = Field(default_factory=StrategyOutput)

    tool_intents: list[ToolIntent] = Field(default_factory=list)
    new_stage: str | None = None
    extracted_insights: Insights = Field(default_factory=Insights)

    thinking: str | None = None
    model_used: str | None = None
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    processing_time_ms: int = 0
