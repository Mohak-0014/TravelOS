from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.agents import budget_optimizer as budget_optimizer_agent
from backend.agents import events as events_agent
from backend.agents import hotel as hotel_agent
from backend.agents import itinerary_planner as itinerary_planner_agent
from backend.agents import packing_list as packing_list_agent
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


async def budget_optimizer_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await budget_optimizer_agent.run(state)


async def events_agent_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await events_agent.run(state)


async def packing_list_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await packing_list_agent.run(state)


async def validation_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await validation_node_module.run(state)


async def conflict_detection_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await conflict_detection_node_module.run(state)


async def approval_gate_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await approval_gate_module.run(state)


async def checkpoint_save_node(state: TravelOSState, config: RunnableConfig) -> dict:  # type: ignore[type-arg]
    return await checkpoint_save_module.run(state, config)


# ── Conditional edge functions ────────────────────────────────────────────────


def route_after_planner(state: TravelOSState) -> str:
    """Initial run joins the hotel branch at budget_optimizer; a replan takes the
    short path straight to validation — hotel/budget/events/packing don't depend
    on the regenerated day plan and must not re-run up to 3 times."""
    if state.get("replan_iterations", 0) > 0:
        return "validation"
    return "budget_optimizer"


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
    g.add_node("budget_optimizer", budget_optimizer_node)
    g.add_node("events_agent", events_agent_node)
    g.add_node("packing_list", packing_list_node)
    g.add_node("validation", validation_node)
    g.add_node("conflict_detection", conflict_detection_node)
    g.add_node("approval_gate", approval_gate_node)
    g.add_node("checkpoint_save", checkpoint_save_node)

    g.set_entry_point("supervisor")

    g.add_edge("supervisor", "travel_style")
    # Fan-out: hotel search only needs trip + style, not the itinerary — run it in
    # parallel with the (much slower) itinerary planner; join at budget_optimizer.
    g.add_edge("travel_style", "itinerary_planner")
    g.add_edge("travel_style", "hotel_agent")
    g.add_conditional_edges(
        "itinerary_planner",
        route_after_planner,
        {
            "budget_optimizer": "budget_optimizer",
            "validation": "validation",
        },
    )
    g.add_edge("hotel_agent", "budget_optimizer")
    g.add_edge("budget_optimizer", "events_agent")
    g.add_edge("events_agent", "packing_list")
    g.add_edge("packing_list", "validation")
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
