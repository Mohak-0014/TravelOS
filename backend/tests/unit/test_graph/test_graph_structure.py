import pytest
from langgraph.checkpoint.memory import MemorySaver

from backend.graphs.replan_graph import build_replan_graph
from backend.graphs.state import TravelOSState
from backend.graphs.trip_graph import build_trip_graph

# ── compilation ───────────────────────────────────────────────────────────────


def test_trip_graph_compiles_without_error() -> None:
    graph = build_trip_graph(checkpointer=MemorySaver())
    assert graph is not None


def test_replan_graph_compiles_without_error() -> None:
    graph = build_replan_graph()
    assert graph is not None


# ── node presence ──────────────────────────────────────────────────────────────


def test_trip_graph_has_all_required_nodes() -> None:
    graph = build_trip_graph(checkpointer=MemorySaver())
    node_names = set(graph.nodes.keys())
    expected = {
        "supervisor",
        "travel_style",
        "itinerary_planner",
        "hotel_agent",
        "events_agent",
        "validation",
        "conflict_detection",
        "approval_gate",
        "checkpoint_save",
    }
    assert expected.issubset(node_names)


def test_replan_graph_has_all_required_nodes() -> None:
    graph = build_replan_graph()
    node_names = set(graph.nodes.keys())
    expected = {"weather_check", "impact_assessment", "weather_adaptation", "create_approvals"}
    assert expected.issubset(node_names)


# ── interrupt configuration ───────────────────────────────────────────────────


def test_trip_graph_interrupts_before_approval_gate() -> None:
    graph = build_trip_graph(checkpointer=MemorySaver())
    assert "approval_gate" in graph.interrupt_before_nodes


# ── stub nodes run without error ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trip_graph_stub_run_completes() -> None:
    """
    Run the full graph with stubs (no LLM, no DB).
    Expects the graph to pause at approval_gate (interrupt_before).
    """
    checkpointer = MemorySaver()
    graph = build_trip_graph(checkpointer=checkpointer)

    initial_state: TravelOSState = {
        "trip_id": "test-trip",
        "user_id": "test-user",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {},
        "hotel_state": {},
        "events_state": {},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "supervisor",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }

    config = {"configurable": {"thread_id": "test-trip"}}
    result = await graph.ainvoke(initial_state, config=config)

    # Graph should have progressed through the stub nodes
    assert result is not None


@pytest.mark.asyncio
async def test_replan_graph_stub_run_completes() -> None:
    graph = build_replan_graph()
    initial_state: TravelOSState = {
        "trip_id": "test-trip",
        "user_id": "test-user",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {},
        "hotel_state": {},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "weather_check",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    result = await graph.ainvoke(initial_state)
    assert result is not None


def test_route_after_planner_short_circuits_on_replan() -> None:
    from backend.graphs.trip_graph import route_after_planner

    # Initial run joins the hotel branch at budget_optimizer
    assert route_after_planner({"replan_iterations": 0}) == "budget_optimizer"  # type: ignore[typeddict-item]
    # A replan takes the short path — hotel/budget/events/packing must not re-run
    assert route_after_planner({"replan_iterations": 1}) == "validation"  # type: ignore[typeddict-item]
