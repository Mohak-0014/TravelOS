from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.agents import hotel as hotel_agent
from backend.agents import itinerary_planner as itinerary_planner_agent
from backend.agents import supervisor as supervisor_agent
from backend.agents import travel_style as travel_style_agent
from backend.core.logging import get_logger
from backend.graphs import approval_gate as approval_gate_module
from backend.graphs import checkpoint_save as checkpoint_save_module
from backend.graphs import conflict_detection as conflict_detection_node_module
from backend.graphs import validation as validation_node_module
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)

# ── Node functions ────────────────────────────────────────────────────────────


async def supervisor_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await supervisor_agent.run(state)


async def travel_style_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await travel_style_agent.run(state)


async def itinerary_planner_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await itinerary_planner_agent.run(state)


async def hotel_agent_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await hotel_agent.run(state)


async def validation_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await validation_node_module.run(state)


async def conflict_detection_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await conflict_detection_node_module.run(state)


async def approval_gate_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await approval_gate_module.run(state)


async def checkpoint_save_node(state: TravelOSState, config: RunnableConfig) -> dict:  # type: ignore[type-arg]
    return await checkpoint_save_module.run(state, config)


# ── Conditional edge functions ────────────────────────────────────────────────


def route_supervisor(state: TravelOSState) -> str:
    if state.get("error_state") and state.get("replan_iterations", 0) >= 3:
        return END
    step = state.get("current_step", "travel_style")
    if step in ("travel_style", "itinerary_planner", "error_recovery"):
        return step
    return "travel_style"


def route_conflict_detection(state: TravelOSState) -> str:
    if state.get("replan_iterations", 0) < 3 and state.get("current_step") == "itinerary_planner":
        return "itinerary_planner"
    return "approval_gate"


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_trip_graph(checkpointer=None):  # type: ignore[no-untyped-def]
    """
    Build and compile the main TravelOS trip planning graph.
    Pass a checkpointer (MemorySaver for tests, AsyncPostgresSaver for prod).
    Compiled with interrupt_before=["approval_gate"] so the graph pauses
    before applying any consequential change, awaiting human approval.
    """
    g = StateGraph(TravelOSState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("travel_style", travel_style_node)
    g.add_node("itinerary_planner", itinerary_planner_node)
    g.add_node("hotel_agent", hotel_agent_node)
    g.add_node("validation", validation_node)
    g.add_node("conflict_detection", conflict_detection_node)
    g.add_node("approval_gate", approval_gate_node)
    g.add_node("checkpoint_save", checkpoint_save_node)

    g.set_entry_point("supervisor")

    g.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "travel_style": "travel_style",
            "itinerary_planner": "itinerary_planner",
            "error_recovery": "supervisor",
            END: END,
        },
    )
    g.add_edge("travel_style", "itinerary_planner")
    g.add_edge("itinerary_planner", "hotel_agent")
    g.add_edge("hotel_agent", "validation")
    g.add_edge("validation", "conflict_detection")
    g.add_conditional_edges(
        "conflict_detection",
        route_conflict_detection,
        {
            "itinerary_planner": "itinerary_planner",
            "approval_gate": "approval_gate",
        },
    )
    g.add_edge("approval_gate", "checkpoint_save")
    g.add_edge("checkpoint_save", END)

    return g.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval_gate"],
    )
