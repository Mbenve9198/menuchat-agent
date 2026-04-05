import time
import logging

from fastapi import APIRouter, HTTPException

from app.api.models import (
    AgentRequest,
    AgentResponse,
    ProactiveRequest,
    ResumeRequest,
)

logger = logging.getLogger("agent-service.routes")
router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "menuchat-agent"}


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
