"""Supervisor agent — validates state, initializes defaults, and coordinates error recovery."""

from __future__ import annotations

import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)

_RECOVERY_SYSTEM = """You are the Supervisor for TravelOS, an AI travel planning system.
Analyze the error and decide whether to retry or abort.

Respond ONLY with valid JSON (no other text):
{
  "recoverable": true or false,
  "retry_node": "travel_style" | "itinerary_planner" | "hotel_agent",
  "reason": "one sentence"
}

Recoverable: transient API failures, timeouts, rate limits, partial data gaps.
Not recoverable: missing required fields, auth failures, repeated errors, data corruption."""

_VALID_RETRY_NODES = frozenset({"travel_style", "itinerary_planner", "hotel_agent"})


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(  # type: ignore[call-arg]
        model="claude-sonnet-4-6",
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=256,
        temperature=0,
    )


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    """Entry point called by supervisor_node in trip_graph.py."""
    trip_id = state.get("trip_id", "unknown")
    error_state = state.get("error_state")

    if error_state:
        return await _handle_error_recovery(state, trip_id, error_state)
    return _handle_fresh_run(state, trip_id)


def _handle_fresh_run(state: TravelOSState, trip_id: str) -> dict:  # type: ignore[type-arg]
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
            "by_category": {"lodging": 0.0, "food": 0.0, "activity": 0.0, "transport": 0.0},
            "breach_pct": 0.0,
        }
    if not state.get("weather_state"):
        updates["weather_state"] = {"risk_flags": [], "last_checked": None}
    if not state.get("hotel_state"):
        updates["hotel_state"] = {"candidates": [], "selected": None}

    return updates


async def _handle_error_recovery(
    state: TravelOSState,
    trip_id: str,
    error_state: dict,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    replan_iterations = state.get("replan_iterations", 0)
    logger.warning(
        "supervisor_error_recovery",
        trip_id=trip_id,
        attempt=replan_iterations + 1,
        error=error_state,
    )

    if replan_iterations >= 3:
        logger.error("supervisor_max_retries_reached", trip_id=trip_id)
        return {
            "current_step": "end",
            "agent_messages": [
                SystemMessage(
                    content=f"Supervisor: max retries reached for trip={trip_id}. Aborting."
                )
            ],
        }

    llm = _build_llm()
    error_summary = json.dumps(error_state, default=str)
    response = await llm.ainvoke(
        [
            SystemMessage(content=_RECOVERY_SYSTEM),
            HumanMessage(
                content=(
                    f"Error for trip {trip_id} "
                    f"(attempt {replan_iterations + 1}/3):\n{error_summary}"
                )
            ),
        ]
    )

    raw = str(response.content) if hasattr(response, "content") else str(response)
    decision = _parse_recovery_decision(raw)

    if not decision["recoverable"]:
        logger.error(
            "supervisor_unrecoverable_error",
            trip_id=trip_id,
            reason=decision["reason"],
        )
        return {
            "current_step": "end",
            "replan_iterations": 3,
            "agent_messages": [
                SystemMessage(
                    content=(
                        f"Supervisor: unrecoverable error for trip={trip_id}: {decision['reason']}"
                    )
                )
            ],
        }

    retry_node = (
        decision["retry_node"]
        if decision["retry_node"] in _VALID_RETRY_NODES
        else "itinerary_planner"
    )
    logger.info(
        "supervisor_retrying",
        trip_id=trip_id,
        retry_node=retry_node,
        reason=decision["reason"],
    )

    return {
        "current_step": retry_node,
        "error_state": None,
        "replan_iterations": replan_iterations + 1,
        "agent_messages": [
            SystemMessage(
                content=(
                    f"Supervisor: recovering trip={trip_id} → retrying {retry_node}. "
                    f"Reason: {decision['reason']}"
                )
            )
        ],
    }


def _parse_recovery_decision(raw: str) -> dict:  # type: ignore[type-arg]
    """Extract JSON from LLM response; falls back to non-recoverable on parse error."""
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            return {
                "recoverable": bool(data.get("recoverable", False)),
                "retry_node": str(data.get("retry_node", "itinerary_planner")),
                "reason": str(data.get("reason", "unknown")),
            }
    except (json.JSONDecodeError, KeyError):
        pass
    return {
        "recoverable": False,
        "retry_node": "itinerary_planner",
        "reason": "failed to parse LLM response",
    }
