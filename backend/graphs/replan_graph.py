from langgraph.graph import END, StateGraph

from backend.agents.weather import (
    create_approvals,
    impact_assessment,
    weather_adaptation,
    weather_check,
)
from backend.core.logging import get_logger
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)


async def weather_check_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await weather_check(state)


async def impact_assessment_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await impact_assessment(state)


async def weather_adaptation_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await weather_adaptation(state)


async def create_approvals_node(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return await create_approvals(state)


def build_replan_graph(checkpointer=None):  # type: ignore[no-untyped-def]
    """
    Replan graph: triggered by Celery Beat when adverse weather is detected for a trip.
    Flow: weather_check → impact_assessment → weather_adaptation → create_approvals → END
    Never mutates the itinerary directly — all changes require user approval.
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
