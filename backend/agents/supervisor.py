"""Supervisor agent — validates state and initializes sub-state defaults.

Historically this module also carried an LLM-driven error-recovery path, but no
graph edge could ever reach it (errors flow through agents' own graceful
degradation instead), so it was removed rather than left as dead code. If real
mid-graph retry routing is ever needed, wire failure edges from the agent nodes
back here first.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage

from backend.core.logging import get_logger
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    """Entry point called by supervisor_node in trip_graph.py."""
    trip_id = state.get("trip_id", "unknown")
    logger.info("supervisor_start", trip_id=trip_id, user_id=state.get("user_id"))

    updates: dict = {  # type: ignore[type-arg]
        "current_step": "travel_style",
        "agent_messages": [
            SystemMessage(
                content=f"Supervisor: starting trip planning pipeline for trip={trip_id}."
            )
        ],
    }

    if not state.get("budget_state"):
        updates["budget_state"] = {
            "total": None,
            "spent": 0.0,
            # Same category vocabulary as budget_optimizer._compute_costs — keep in sync
            "by_category": {
                "lodging": 0.0,
                "activities": 0.0,
                "meals": 0.0,
                "transport": 0.0,
                "flights": 0.0,
            },
            "breach_pct": 0.0,
        }
    if not state.get("weather_state"):
        updates["weather_state"] = {"risk_flags": [], "last_checked": None}
    if not state.get("hotel_state"):
        updates["hotel_state"] = {"candidates": [], "selected": None}
    if not state.get("events_state"):
        updates["events_state"] = {
            "fetched": 0,
            "filtered": 0,
            "proposed": [],
            "conflict_warnings": 0,
        }
    if not state.get("replan_feedback"):
        updates["replan_feedback"] = []

    return updates
