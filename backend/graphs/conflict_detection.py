"""Conflict Detection node — checks business rules and triggers replanning or approvals."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import time as dt_time

from langchain_core.messages import SystemMessage

from backend.core.logging import get_logger
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)

# Budget breach threshold that requires human approval (from GUARDRAILS)
_BUDGET_BREACH_THRESHOLD_PCT = 15.0

# Maximum items per day before flagging as over-packed
_MAX_ITEMS_PER_DAY = 8


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    itinerary: list[dict] = list(state.get("itinerary") or [])  # type: ignore[arg-type]
    weather_state: dict = dict(state.get("weather_state") or {})  # type: ignore[type-arg]
    budget_state: dict = dict(state.get("budget_state") or {})  # type: ignore[type-arg]
    hotel_state: dict = dict(state.get("hotel_state") or {})  # type: ignore[type-arg]
    replan_iterations: int = state.get("replan_iterations", 0)
    approvals: list[dict] = list(state.get("approval_queue") or [])  # type: ignore[arg-type]

    logger.info("conflict_detection_start", trip_id=trip_id, items=len(itinerary))

    conflicts: list[str] = []
    should_replan = False

    # ── 1. Time overlaps ──────────────────────────────────────────────────────
    overlap_days = _find_time_overlaps(itinerary)
    if overlap_days:
        conflicts.append(f"Time overlaps on day(s): {overlap_days}")
        should_replan = True

    # ── 2. All-default itinerary (LLM fallback) ───────────────────────────────
    if itinerary and all(it.get("item_type") == "free" for it in itinerary):
        conflicts.append(
            "All items are unplanned 'free' blocks — itinerary generation likely failed"
        )
        should_replan = True

    # ── 3. Budget breach ──────────────────────────────────────────────────────
    estimated = budget_state.get("estimated_planned", 0.0)
    budget_total = budget_state.get("total")
    currency = str(budget_state.get("currency") or "INR")
    if budget_total and float(estimated) > 0:
        breach_pct = (float(estimated) - float(budget_total)) / float(budget_total) * 100
        if breach_pct > _BUDGET_BREACH_THRESHOLD_PCT:
            conflicts.append(
                f"Budget breach: estimated {currency} {float(estimated):.0f} vs "
                f"{currency} {float(budget_total):.0f} ({breach_pct:.0f}% over)"
            )
            approvals.append(_budget_approval(estimated, budget_total, breach_pct, currency))
            budget_state["breach_pct"] = round(breach_pct, 1)

    # ── 4. Over-packed days ───────────────────────────────────────────────────
    items_per_day: dict[int, int] = defaultdict(int)
    for it in itinerary:
        items_per_day[it.get("day_number", 0)] += 1
    packed = [d for d, n in items_per_day.items() if n > _MAX_ITEMS_PER_DAY]
    if packed:
        conflicts.append(f"Over-packed day(s) (>{_MAX_ITEMS_PER_DAY} items): {sorted(packed)}")

    # ── 5. Adverse weather with outdoor activities ────────────────────────────
    risk_flags = set(weather_state.get("risk_flags", []))
    if risk_flags:
        outdoor_on_adverse = [
            it["title"]
            for it in itinerary
            if it.get("is_outdoor") and it.get("item_date") in risk_flags
        ]
        if outdoor_on_adverse:
            conflicts.append(
                f"{len(outdoor_on_adverse)} outdoor activity(ies) on adverse weather day(s) "
                f"— weather agent will handle"
            )

    # ── 6. No hotel selected ──────────────────────────────────────────────────
    if not hotel_state.get("selected"):
        conflicts.append("No hotel selected — hotel search returned no results")

    # ── Routing decision ──────────────────────────────────────────────────────
    next_step = "approval_gate"
    new_iterations = replan_iterations

    if should_replan and replan_iterations < 3:
        next_step = "itinerary_planner"
        new_iterations = replan_iterations + 1
        conflicts.append(f"Triggering replan (attempt {new_iterations}/3)")

    n = len(conflicts)
    summary = f"{n} conflict(s) detected" if n else "No conflicts"
    if next_step == "itinerary_planner":
        summary += " — replanning itinerary"

    logger.info(
        "conflict_detection_complete",
        trip_id=trip_id,
        conflicts=n,
        next_step=next_step,
        replan_iterations=new_iterations,
    )

    return {
        "current_step": next_step,
        "replan_iterations": new_iterations,
        "approval_queue": approvals,
        "budget_state": budget_state,
        "agent_messages": [
            SystemMessage(
                content=(
                    f"Conflict Detection [trip={trip_id}]: {summary}."
                    + (f" Details: {'; '.join(conflicts)}" if conflicts else "")
                )
            )
        ],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _find_time_overlaps(itinerary: list[dict]) -> list[int]:  # type: ignore[type-arg]
    """Return sorted list of day numbers that contain at least one time overlap."""
    day_windows: dict[int, list[tuple[dt_time, dt_time]]] = defaultdict(list)

    for item in itinerary:
        start = _parse_time(item.get("start_time"))
        end = _parse_time(item.get("end_time"))
        day = item.get("day_number", 0)
        if start and end and start < end:
            day_windows[day].append((start, end))

    overlapping: list[int] = []
    for day, windows in day_windows.items():
        windows.sort(key=lambda w: w[0])
        for i in range(len(windows) - 1):
            if windows[i][1] > windows[i + 1][0]:
                overlapping.append(day)
                break

    return sorted(overlapping)


def _budget_approval(
    estimated: float,
    budget_total: float,
    breach_pct: float,
    currency: str = "INR",
) -> dict:  # type: ignore[type-arg]
    return {
        "id": str(uuid.uuid4()),
        "proposed_by": "conflict_detection",
        "change_type": "budget_exceed",
        "summary": (
            f"Estimated itinerary cost {currency} {float(estimated):.0f} exceeds "
            f"budget {currency} {float(budget_total):.0f} by {breach_pct:.0f}%"
        ),
        "payload": {
            "estimated_total": round(float(estimated), 2),
            "budget_total": round(float(budget_total), 2),
            "breach_pct": round(breach_pct, 1),
            "currency": currency,
        },
        "status": "pending",
    }


def _parse_time(t: object) -> dt_time | None:
    if not isinstance(t, str):
        return None
    try:
        parts = t.split(":")
        return dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None
