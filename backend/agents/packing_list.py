"""Packing List agent — generates a context-aware, categorized packing checklist."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
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

        logger.info(
            "packing_list_done",
            trip_id=trip_id,
            category_count=len(packing.get("categories", {})),
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

    risk_flags: list[str] = list(weather_state.get("risk_flags") or [])  # type: ignore[arg-type]

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

    llm = build_llm(size="small", temperature=0.3)
    resp = llm.invoke([SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)])
    raw = str(resp.content).strip()

    # Strip markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.replace("```", "").strip()

    return dict(json.loads(raw))  # type: ignore[arg-type]


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
