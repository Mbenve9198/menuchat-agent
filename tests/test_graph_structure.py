"""Test that the LangGraph state machines are correctly structured."""

from app.graph.reactive_graph import build_reactive_graph
from app.graph.proactive_graph import build_proactive_graph


def test_reactive_graph_has_all_nodes():
    graph = build_reactive_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "complexity_router", "researcher", "memory_recall", "strategist",
        "strategy_critic", "writer", "reviewer", "hibernate", "build_response",
    }
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


def test_proactive_graph_has_all_nodes():
    graph = build_proactive_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "researcher", "memory_recall", "strategist", "strategy_critic",
        "writer", "reviewer", "hibernate", "build_response",
    }
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


def test_proactive_graph_has_no_complexity_router():
    graph = build_proactive_graph()
    assert "complexity_router" not in graph.nodes
