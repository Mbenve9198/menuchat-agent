import time
import logging

from fastapi import APIRouter, HTTPException

from app.api.models import (
    AgentRequest,
    AgentResponse,
    FeedbackRequest,
    ProactiveRequest,
    ResumeRequest,
)

logger = logging.getLogger("agent-service.routes")
router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "menuchat-agent"}


@router.get("/debug/config")
async def debug_config():
    """Temporary: verify env vars are set correctly. Remove after debugging."""
    from app.config import get_settings
    s = get_settings()
    def mask(v):
        if not v: return "NOT SET"
        if len(v) <= 6: return v[:2] + "***"
        return v[:4] + "***" + v[-3:]
    return {
        "anthropic_key": mask(s.anthropic_api_key),
        "serpapi_key": mask(s.serpapi_key),
        "menuchat_backend_url": s.menuchat_backend_url or "NOT SET",
        "crm_api_key": mask(s.crm_api_key),
        "crm_api_key_length": len(s.crm_api_key) if s.crm_api_key else 0,
        "crm_api_key_repr": repr(s.crm_api_key) if s.crm_api_key else "NOT SET",
        "smartlead_api_key": mask(s.smartlead_api_key),
        "postgres_url": mask(s.postgres_url),
    }


@router.post("/agent/process", response_model=AgentResponse)
async def process_reactive(request: AgentRequest):
    """Reactive flow: lead sent a message, generate a response."""
    start = time.perf_counter()
    logger.info(
        "process_reactive | conv=%s contact=%s source=%s stage=%s",
        request.conversation_id,
        request.contact.email,
        request.lead_source,
        request.stage,
    )

    try:
        from app.graph.reactive_graph import run_reactive

        result = await run_reactive(request)
        result.processing_time_ms = int((time.perf_counter() - start) * 1000)
        return result
    except Exception as e:
        logger.exception("process_reactive failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/proactive", response_model=AgentResponse)
async def process_proactive(request: ProactiveRequest):
    """Proactive flow: agent-initiated action (outreach, follow-up, break-up, reactivation)."""
    start = time.perf_counter()
    logger.info(
        "process_proactive | type=%s contact=%s conv=%s",
        request.task_type,
        request.contact.email,
        request.conversation_id,
    )

    try:
        from app.graph.proactive_graph import run_proactive

        result = await run_proactive(request)
        result.processing_time_ms = int((time.perf_counter() - start) * 1000)
        return result
    except Exception as e:
        logger.exception("process_proactive failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/resume", response_model=AgentResponse)
async def resume_workflow(request: ResumeRequest):
    """Resume a hibernated workflow from a PostgreSQL checkpoint (Durable Execution)."""
    start = time.perf_counter()
    logger.info("resume_workflow | thread=%s", request.thread_id)

    try:
        from app.graph.reactive_graph import resume_hibernated

        result = await resume_hibernated(request)
        result.processing_time_ms = int((time.perf_counter() - start) * 1000)
        return result
    except Exception as e:
        logger.exception("resume_workflow failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/feedback")
async def store_feedback(request: FeedbackRequest):
    """Store human feedback as an episodic memory for future learning."""
    logger.info(
        "store_feedback | conv=%s action=%s contact=%s",
        request.conversation_id, request.action, request.contact_email,
    )

    try:
        from app.memory.manager import store_feedback

        ctx = request.conversation_context
        episode = {
            "lead_profile": request.lead_profile,
            "situation": ctx.get("leadLastMessage", ""),
            "objections": ctx.get("objections", []),
            "task_type": ctx.get("source", ""),
            "stage": ctx.get("stage", ""),
            "strategy": "",
            "strategy_reasoning": "",
            "draft": request.agent_draft,
            "outcome": request.action,
            "human_edits": {
                "final_sent": request.final_sent,
                "modifications": request.modifications,
                "discard_reason": request.discard_reason,
                "discard_notes": request.discard_notes,
            },
            "conversation_id": request.conversation_id,
            "contact_email": request.contact_email,
        }

        point_id = await store_feedback(episode)
        return {"status": "stored", "point_id": point_id}
    except Exception as e:
        logger.exception("store_feedback failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
