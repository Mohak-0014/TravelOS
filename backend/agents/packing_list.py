"""Packing List agent — generates a context-aware, categorized packing checklist."""

from __future__ import annotations

import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import select, update

from backend.agents._llm import build_llm
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import ItineraryItem, Trip
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a travel packing expert. Generate a practical, context-aware packing list.\n\n"
    "Respond ONLY with valid JSON — no markdown fences, no extra text:\n"
    '{\n  "categories": {\n'
    '    "Documents & Money": ["Passport", "Travel insurance printout", "Credit cards"],\n'
    '    "Clothing": ["..."],\n'
    '    "Electronics": ["..."],\n'
    '    "Health & Toiletries": ["..."],\n'
    '    "Accessories": ["..."],\n'
    '    "Destination-Specific": ["..."]\n'
    "  }\n}\n\n"
    "Guidelines:\n"
    '- Be specific (e.g. "Lightweight rain jacket" not "jacket")\n'
    '- Quantity hints for consumables ("Sunscreen x2 for 7 days")\n'
    "- Add weather-appropriate items based on season and climate risks\n"
    "- Add activity-specific gear (hiking boots for hiking, formal wear for fine dining)\n"
    "- Include Destination-Specific items unique to the country/city\n"
    "- Keep total across all categories under 45 items"
)


async def run(state: TravelOSState) -> dict[str, object]:
    trip_id = state.get("trip_id", "unknown")
    logger.info("packing_list_start", trip_id=trip_id)

    try:
        trip = await _load_trip(trip_id)
        if trip is None:
            logger.warning("packing_list_no_trip", trip_id=trip_id)
            return {"packing_state": {"categories": {}, "status": "skipped"}}

        items = await _load_itinerary_items(trip_id)
        weather_state: dict[str, object] = dict(state.get("weather_state") or {})  # type: ignore[arg-type]

        packing = await _generate(trip, items, weather_state)
        await _persist(trip_id, packing)

        cats = packing.get("categories", {})
        logger.info(
            "packing_list_done",
            trip_id=trip_id,
            category_count=len(cats) if isinstance(cats, dict) else 0,
        )
        return {"packing_state": {**packing, "status": "done"}}

    except Exception as exc:
        logger.error("packing_list_failed", trip_id=trip_id, error=str(exc))
        return {"packing_state": {"categories": {}, "status": "error", "error": str(exc)}}


async def _load_trip(trip_id: str) -> Trip | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Trip).where(Trip.id == trip_id))
        return result.scalar_one_or_none()


async def _load_itinerary_items(trip_id: str) -> list[ItineraryItem]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ItineraryItem)
            .where(ItineraryItem.trip_id == trip_id)
            .order_by(ItineraryItem.day_number)
        )
        return list(result.scalars().all())


async def _generate(
    trip: Trip, items: list[ItineraryItem], weather_state: dict[str, object]
) -> dict[str, object]:
    duration = (trip.end_date - trip.start_date).days + 1
    month = trip.start_date.month
    season = _season(month, trip.destination_country or "")

    # Summarise activities so the LLM can tailor the list
    activity_types: list[str] = []
    for it in items:
        if it.item_type in ("activity", "meal") and it.title:
            activity_types.append(it.title)

    raw_flags = weather_state.get("risk_flags") or []
    risk_flags: list[str] = [str(f) for f in raw_flags] if isinstance(raw_flags, list) else []

    user_msg = (
        f"Destination: {trip.destination_city}, {trip.destination_country or 'unknown country'}\n"
        f"Trip duration: {duration} day{'s' if duration > 1 else ''} "
        f"({trip.start_date} to {trip.end_date})\n"
        f"Season: {season}\n"
        f"Travelers: {trip.num_travelers}\n"
        f"Planned activities: {', '.join(activity_types[:20]) if activity_types else 'general sightseeing'}\n"  # noqa: E501
        f"Weather risks: {', '.join(risk_flags) if risk_flags else 'none noted'}\n"
        f"Budget tier: {getattr(trip, 'budget_tier', 'balanced')}\n"
        "Generate a practical, complete packing list."
    )

    # Cap the completion so the small model can't run away and emit a truncated,
    # unparseable payload (the failure mode that left some trips with no list).
    llm = build_llm(size="small", temperature=0.3, max_tokens=2048)
    messages: list[BaseMessage] = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    last_error = "no response"
    for attempt in range(2):
        resp = llm.invoke(messages)
        raw = _strip_fences(str(resp.content).strip())
        parsed = _safe_parse(raw)
        if parsed and isinstance(parsed.get("categories"), dict) and parsed["categories"]:
            if attempt > 0:
                logger.info("packing_list_recovered", attempt=attempt)
            return parsed

        last_error = "empty or unparseable JSON"
        # One stricter retry before giving up.
        messages.append(
            HumanMessage(
                content=(
                    "That response was not valid JSON or was truncated. Reply again with "
                    "STRICT, COMPLETE JSON only — at most 6 categories and 35 items total, "
                    "no commentary and no markdown."
                )
            )
        )

    raise ValueError(f"packing JSON unusable after retries: {last_error}")


def _strip_fences(raw: str) -> str:
    """Drop markdown fences / surrounding prose so the payload is just the JSON object.

    Handles fences even when the model adds preamble before them
    (e.g. ``Here you go:\\n```json\\n{...}```\\n``).
    """
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) >= 3 else raw.replace("```", "")
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
        raw = raw.strip()
    # Trim to the JSON object boundaries; leave truncated payloads (no closing
    # brace) intact so _safe_parse can salvage them.
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw[start:] if start > 0 else raw


def _safe_parse(raw: str) -> dict[str, object] | None:
    """Parse packing JSON, salvaging a partial list from a truncated response."""
    try:
        return dict(json.loads(raw))
    except json.JSONDecodeError:
        pass
    try:
        return dict(json.loads(_repair_truncated_json(raw)))
    except (json.JSONDecodeError, ValueError):
        return None


def _repair_truncated_json(raw: str) -> str:
    """Best-effort close a packing payload that was cut off mid-array.

    Shape is ``{"categories": {"Cat": [..], ...}}``. Trim back to the last
    completed category array (last ``]``), drop a trailing comma, then balance
    the still-open braces so the partial list is recoverable.
    """
    end = raw.rfind("]")
    if end == -1:
        raise ValueError("nothing salvageable")
    s = raw[: end + 1].rstrip().rstrip(",")
    opens = s.count("{") - s.count("}")
    return s + ("}" * opens if opens > 0 else "")


async def _persist(trip_id: str, packing: dict[str, object]) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(update(Trip).where(Trip.id == trip_id).values(packing_list=packing))
        await session.commit()


def _season(month: int, country: str) -> str:
    """Rough Northern/Southern hemisphere season guess from month."""
    southern = {"australia", "new zealand", "argentina", "brazil", "south africa", "chile"}
    is_southern = any(c in country.lower() for c in southern)

    if is_southern:
        if month in (12, 1, 2):
            return "summer (hot)"
        elif month in (3, 4, 5):
            return "autumn"
        elif month in (6, 7, 8):
            return "winter (cold)"
        else:
            return "spring"
    else:
        if month in (12, 1, 2):
            return "winter (cold)"
        elif month in (3, 4, 5):
            return "spring"
        elif month in (6, 7, 8):
            return "summer (hot)"
        else:
            return "autumn"
