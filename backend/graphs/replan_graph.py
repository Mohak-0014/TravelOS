from langgraph.graph import END, StateGraph

from backend.core.logging import get_logger
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)

# ── Stub nodes — fully implemented in Week 15 ─────────────────────────────────

async def weather_check_node(state: TravelOSState) -> dict:
    logger.info("weather_check_node_stub", trip_id=state.get("trip_id"))
    return {"current_step": "impact_assessment"}


async def impact_assessment_node(state: TravelOSState) -> dict:
    logger.info("impact_assessment_node_stub", trip_id=state.get("trip_id"))
    return {"current_step": "weather_adaptation"}


async def weather_adaptation_node(state: TravelOSState) -> dict:
    logger.info("weather_adaptation_node_stub", trip_id=state.get("trip_id"))
    return {"current_step": "create_approvals"}


async def create_approvals_node(state: TravelOSState) -> dict:
    logger.info("create_approvals_node_stub", trip_id=state.get("trip_id"))
    return {"current_step": "end"}


def build_replan_graph(checkpointer=None):  # type: ignore[no-untyped-def]
    """
    Replan graph: triggered by Celery Beat when adverse weather is detected.
    Always ends by creating approval records — never mutates the itinerary directly.
    Full implementation in Week 15.
    """
    g = StateGraph(TravelOSState)

    g.add_node("weather_check", weather_check_node)
    g.add_node("impact_assessment", impact_assessment_node)
    g.add_node("weather_adaptation", weather_adaptation_node)
    g.add_node("create_approvals", create_approvals_node)

    g.set_entry_point("weather_check")
    g.add_edge("weather_check", "impact_assessment")
    g.add_edge("impact_assessment", "weather_adaptation")
    g.add_edge("weather_adaptation", "create_approvals")
    g.add_edge("create_approvals", END)

    return g.compile(checkpointer=checkpointer)
