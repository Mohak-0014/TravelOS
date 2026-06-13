"""Validation node — cleans and sanity-checks the itinerary before conflict detection."""

from __future__ import annotations

from datetime import time as dt_time

from langchain_core.messages import SystemMessage

from backend.core.logging import get_logger
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)

_VALID_ITEM_TYPES = frozenset({"activity", "meal", "transport", "lodging", "free"})

# Minimum items per day before flagging for replan (pace_target - 1)
_PACE_MIN_ITEMS: dict[str, int] = {"relaxed": 2, "moderate": 3, "packed": 5}


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    raw_items: list[dict] = list(state.get("itinerary") or [])  # type: ignore[arg-type]

    memory_context = state.get("memory_context") or {}
    prefs = memory_context.get("preferences") or {}
    pace = str(prefs.get("pace") or "moderate")

    logger.info("validation_start", trip_id=trip_id, item_count=len(raw_items))

    issues: list[str] = []
    cleaned: list[dict] = []  # type: ignore[type-arg]
    sort_counters: dict[int, int] = {}

    for raw in raw_items:
        item, item_issues = _validate_and_fix(raw)
        issues.extend(item_issues)
        if item is not None:
            day = item.get("day_number", 1)
            sort_counters[day] = sort_counters.get(day, -1) + 1
            item["sort_order"] = sort_counters[day]
            cleaned.append(item)

    removed = len(raw_items) - len(cleaned)
    if removed:
        issues.append(f"{removed} item(s) dropped (empty title or invalid day_number)")

    if not cleaned:
        issues.append("Itinerary is empty after validation")

    # Pace-based under-count check: flag days below pace_target - 1
    min_items = _PACE_MIN_ITEMS.get(pace, 3)
    day_counts: dict[int, int] = {}
    for it in cleaned:
        day_num = int(it.get("day_number", 1))
        day_counts[day_num] = day_counts.get(day_num, 0) + 1
    for day_num, count in sorted(day_counts.items()):
        if count < min_items:
            issues.append(
                f"Day {day_num} has {count} item(s) — below pace minimum of {min_items}"
                f" for '{pace}' pace"
            )

    # Compute total planned cost and write it into budget_state for conflict detection
    estimated_total = sum(float(it.get("est_cost") or 0) for it in cleaned)
    budget_state: dict = dict(state.get("budget_state") or {})  # type: ignore[type-arg]
    if estimated_total > 0:
        budget_state["estimated_planned"] = round(estimated_total, 2)

    summary = (
        f"{len(cleaned)} items valid"
        + (f", {removed} removed" if removed else "")
        + (f". Issues: {'; '.join(issues[:3])}" if issues else ". No issues.")
    )
    logger.info("validation_complete", trip_id=trip_id, valid=len(cleaned), removed=removed)

    return {
        "itinerary": cleaned,
        "budget_state": budget_state,
        "agent_messages": [SystemMessage(content=f"Validation [trip={trip_id}]: {summary}")],
    }


def _validate_and_fix(raw: dict) -> tuple[dict | None, list[str]]:  # type: ignore[type-arg]
    """
    Return (cleaned_item, issues) — or (None, issues) if the item must be dropped.
    Modifies a copy; never mutates the input.
    """
    item = dict(raw)
    issues: list[str] = []

    # Drop items missing a title
    title = str(item.get("title") or "").strip()
    if not title:
        issues.append("Dropped item: empty title")
        return None, issues
    item["title"] = title

    # Drop items with non-positive day_number
    day = item.get("day_number")
    if not isinstance(day, int) or day < 1:
        issues.append(f"Dropped item '{title}': invalid day_number={day!r}")
        return None, issues

    # Coerce invalid item_type to "free"
    if item.get("item_type") not in _VALID_ITEM_TYPES:
        issues.append(f"Item '{title}': unknown item_type={item.get('item_type')!r} → 'free'")
        item["item_type"] = "free"

    # Fix swapped start/end times
    start = _parse_time(item.get("start_time"))
    end = _parse_time(item.get("end_time"))
    if start and end and end < start:
        issues.append(f"Item '{title}': end_time before start_time — swapped")
        item["start_time"], item["end_time"] = item["end_time"], item["start_time"]

    # Nullify negative costs
    est_cost = item.get("est_cost")
    if est_cost is not None and float(est_cost) < 0:
        issues.append(f"Item '{title}': negative est_cost={est_cost} → null")
        item["est_cost"] = None

    # Ensure boolean is_outdoor
    item["is_outdoor"] = bool(item.get("is_outdoor", False))

    return item, issues


def _parse_time(t: object) -> dt_time | None:
    if not isinstance(t, str):
        return None
    try:
        parts = t.split(":")
        return dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None
