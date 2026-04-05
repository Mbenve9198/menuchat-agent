"""
Proactive LangGraph — agent-initiated actions (outreach, follow-up, break-up, reactivation).
Same pipeline as reactive but always takes the "complex" path (needs research).
"""

import logging
import uuid

from langgraph.graph import StateGraph, END

from app.api.models import AgentResponse, ProactiveRequest
from app.db import get_checkpointer
from app.graph.state import AgentState
from app.graph.nodes.researcher import researcher_node
from app.graph.nodes.memory_recall import memory_recall_node
from app.graph.nodes.strategist import strategist_node
from app.graph.nodes.strategy_critic import strategy_critic_node
from app.graph.nodes.writer import writer_node
from app.graph.nodes.reviewer import reviewer_node
from app.graph.nodes.hibernate import hibernate_node
from app.graph.nodes.build_response import build_response_node

logger = logging.getLogger("agent-service.graph.proactive")


def _route_after_strategy(state: AgentState) -> str:
    strategy = state.get("strategy", {})
    if strategy.get("hibernate"):
        return "hibernate"
    if strategy.get("escalate_human"):
        return "build_response"
    return "strategy_critic"


def _route_strategy_review(state: AgentState) -> str:
    if state.get("strategy_approved"):
        return "writer"
    if state.get("strategy_attempts", 0) >= 3:
        return "build_response"
    return "strategist"


def _route_review_result(state: AgentState) -> str:
    review = state.get("review_result", {})
    if review.get("pass"):
        return "build_response"
    if state.get("review_attempts", 0) >= 2:
        return "build_response"
    return "writer"


def build_proactive_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("researcher", researcher_node)
    graph.add_node("memory_recall", memory_recall_node)
    graph.add_node("strategist", strategist_node)
    graph.add_node("strategy_critic", strategy_critic_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("hibernate", hibernate_node)
    graph.add_node("build_response", build_response_node)

    graph.set_entry_point("researcher")

    graph.add_edge("researcher", "memory_recall")
    graph.add_edge("memory_recall", "strategist")

    graph.add_conditional_edges("strategist", _route_after_strategy, {
        "strategy_critic": "strategy_critic",
        "hibernate": "hibernate",
        "build_response": "build_response",
    })

    graph.add_conditional_edges("strategy_critic", _route_strategy_review, {
        "writer": "writer",
        "strategist": "strategist",
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
        graph = build_proactive_graph()
        _compiled = graph.compile(checkpointer=checkpointer)
    return _compiled


async def run_proactive(request: ProactiveRequest) -> AgentResponse:
    compiled = await _get_compiled()

    thread_id = f"proactive_{request.contact.email}_{uuid.uuid4().hex[:8]}"

    initial_state: AgentState = {
        "request": request,
        "request_type": "proactive",
        "thread_id": thread_id,
        "complexity": "complex",
        "strategy": None,
        "strategy_approved": False,
        "strategy_feedback": None,
        "strategy_attempts": 0,
        "draft": None,
        "review_result": None,
        "review_attempts": 0,
        "episodic_examples": [],
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
