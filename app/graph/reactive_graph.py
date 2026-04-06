"""
Reactive LangGraph — responds to lead messages.
Pipeline: researcher → memory → strategist → writer → reviewer
"""

import logging
import uuid

from langgraph.graph import StateGraph, END

from app.api.models import AgentRequest, AgentResponse, ResumeRequest
from app.db import get_checkpointer
from app.graph.state import AgentState
from app.graph.nodes.researcher import researcher_node
from app.graph.nodes.memory_recall import memory_recall_node
from app.graph.nodes.strategist import strategist_node
from app.graph.nodes.writer import writer_node
from app.graph.nodes.reviewer import reviewer_node
from app.graph.nodes.hibernate import hibernate_node
from app.graph.nodes.build_response import build_response_node

logger = logging.getLogger("agent-service.graph.reactive")


def _route_after_strategy(state: AgentState) -> str:
    strategy = state.get("strategy") or {}
    if strategy.get("hibernate"):
        return "hibernate"
    if strategy.get("escalate_human"):
        return "build_response"
    return "writer"


def _route_review_result(state: AgentState) -> str:
    review = state.get("review_result") or {}
    if review.get("pass"):
        return "build_response"
    if state.get("review_attempts", 0) >= 2:
        return "build_response"
    return "writer"


def build_reactive_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("researcher", researcher_node)
    graph.add_node("memory_recall", memory_recall_node)
    graph.add_node("strategist", strategist_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("hibernate", hibernate_node)
    graph.add_node("build_response", build_response_node)

    graph.set_entry_point("researcher")

    graph.add_edge("researcher", "memory_recall")
    graph.add_edge("memory_recall", "strategist")

    graph.add_conditional_edges("strategist", _route_after_strategy, {
        "writer": "writer",
        "hibernate": "hibernate",
        "build_response": "build_response",
    })

    graph.add_edge("writer", "reviewer")

    graph.add_conditional_edges("reviewer", _route_review_result, {
        "build_response": "build_response",
        "writer": "writer",
    })

    graph.add_edge("hibernate", "build_response")
    graph.add_edge("build_response", END)

    return graph


_compiled = None


async def _get_compiled():
    global _compiled
    if _compiled is None:
        checkpointer = get_checkpointer()
        graph = build_reactive_graph()
        _compiled = graph.compile(checkpointer=checkpointer)
    return _compiled


async def run_reactive(request: AgentRequest) -> AgentResponse:
    compiled = await _get_compiled()

    thread_id = f"{request.conversation_id}_{uuid.uuid4().hex[:8]}"

    initial_state: AgentState = {
        "request": request,
        "request_type": "reactive",
        "thread_id": thread_id,
        "strategy": None,
        "draft": None,
        "review_result": None,
        "review_attempts": 0,
        "episodic_examples": [],
        "contact_memories": [],
        "tool_intents": [],
        "response": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = await compiled.ainvoke(initial_state, config)

    response = result.get("response")
    if response is None:
        response = AgentResponse(action="error", draft=None, channel="email")

    return response


async def resume_hibernated(request: ResumeRequest) -> AgentResponse:
    compiled = await _get_compiled()

    config = {"configurable": {"thread_id": request.thread_id}}
    result = await compiled.ainvoke(
        {"wake_context": request.updated_context, "request_type": "resume"},
        config,
    )

    response = result.get("response")
    if response is None:
        response = AgentResponse(action="error", draft=None, channel="email")

    return response
