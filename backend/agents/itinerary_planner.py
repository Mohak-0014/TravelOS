"""Itinerary Planner agent — fetches real data and generates a day-by-day itinerary via LLM."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from datetime import time as dt_time

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, select

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import ItineraryItem, Trip
from backend.graphs.state import TravelOSState
from backend.tools.geocode import geocode
from backend.tools.places import Attraction, search_attractions
from backend.tools.weather import WeatherDay, fetch_weather

logger = get_logger(__name__)

_VALID_ITEM_TYPES = frozenset({"activity", "meal", "transport", "lodging", "free"})

_SYSTEM_PROMPT = """You are the Itinerary Planner for TravelOS, an AI travel planning system.
Generate a realistic, day-by-day travel itinerary using the trip data, traveler style profile,
weather forecast, and list of real attractions provided.

Rules:
- Use attractions from the provided list whenever possible (exact name, lat, lng, source_ref).
- Schedule indoor activities (museums, galleries) on adverse weather days.
- Respect the traveler's daily rhythm and pace from the style profile.
- Every item must have a valid item_type: activity | meal | transport | lodging | free
- Meals should be realistic for the destination (breakfast, lunch, dinner cadence).
- Times use "HH:MM" 24-hour format. Leave null if genuinely unknown.
- est_cost is in the trip's currency. Omit (null) if unknown.
- is_outdoor is true for parks, viewpoints, walking tours, outdoor sites.

Respond ONLY with a valid JSON array (no other text):
[
  {
    "day_number": 1,
    "item_date": "YYYY-MM-DD",
    "start_time": "09:00",
    "end_time": "12:00",
    "item_type": "activity",
    "title": "...",
    "description": "...",
    "latitude": 48.8606,
    "longitude": 2.3376,
    "address": "...",
    "source_provider": "overpass",
    "source_ref": "way/123456",
    "est_cost": 20.0,
    "est_cost_currency": "EUR",
    "is_outdoor": false,
    "sort_order": 0
  }
]"""


class _ItemDraft(BaseModel):
    day_number: int
    item_date: str  # "YYYY-MM-DD" — validated later against trip dates
    start_time: str | None = None
    end_time: str | None = None
    item_type: str = "activity"
    title: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    source_provider: str | None = None
    source_ref: str | None = None
    est_cost: float | None = None
    est_cost_currency: str | None = None
    is_outdoor: bool = False
    sort_order: int = 0


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(  # type: ignore[call-arg]
        model="claude-sonnet-4-6",
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=8192,
        temperature=0.7,
    )


# ── Entry point ───────────────────────────────────────────────────────────────


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    logger.info("itinerary_planner_start", trip_id=trip_id)

    trip = await _load_trip(trip_id)
    if trip is None:
        logger.error("itinerary_planner_trip_not_found", trip_id=trip_id)
        return {
            "error_state": {"node": "itinerary_planner", "message": f"Trip {trip_id} not found"},
            "agent_messages": [
                SystemMessage(content=f"Itinerary Planner: trip {trip_id} not found in DB.")
            ],
        }

    coords = await _resolve_coords(trip)

    # Fetch weather and attractions in parallel — both degrade gracefully to []
    if coords:
        lat, lng = coords
        weather_days, attractions = await asyncio.gather(
            fetch_weather(lat, lng, trip.start_date, trip.end_date),
            search_attractions(lat, lng, radius_m=5000, limit=30),
        )
    else:
        logger.warning("itinerary_planner_no_coords", trip_id=trip_id)
        weather_days, attractions = [], []

    style_profile = (state.get("memory_context") or {}).get("travel_style_profile", {})
    budget_state = state.get("budget_state") or {}

    items = await _generate_itinerary(trip, style_profile, weather_days, attractions, budget_state)

    if items:
        await _persist_itinerary_items(trip_id, trip, items)
    else:
        logger.warning("itinerary_planner_empty_result", trip_id=trip_id)

    weather_state = _build_weather_state(weather_days)
    itinerary_dicts = [_item_to_dict(it) for it in items]

    logger.info("itinerary_planner_complete", trip_id=trip_id, items=len(items))

    return {
        "itinerary": itinerary_dicts,
        "weather_state": weather_state,
        "agent_messages": [
            SystemMessage(
                content=(
                    f"Itinerary Planner: generated {len(items)} items for trip={trip_id}. "
                    f"Adverse weather days: {weather_state.get('risk_flags', [])}"
                )
            )
        ],
    }


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _load_trip(trip_id: str) -> Trip | None:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Trip).where(Trip.id == trip_id))
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("itinerary_planner_db_load_error", trip_id=trip_id, error=str(exc))
        return None


async def _persist_itinerary_items(trip_id: str, trip: Trip, items: list[_ItemDraft]) -> None:
    try:
        async with AsyncSessionLocal() as session:
            # Delete any existing items so this is idempotent on replan
            await session.execute(delete(ItineraryItem).where(ItineraryItem.trip_id == trip_id))
            for item in items:
                session.add(
                    ItineraryItem(
                        trip_id=trip_id,
                        day_number=item.day_number,
                        item_date=date.fromisoformat(item.item_date),
                        start_time=_parse_time(item.start_time),
                        end_time=_parse_time(item.end_time),
                        item_type=item.item_type,
                        title=item.title,
                        description=item.description,
                        latitude=item.latitude,
                        longitude=item.longitude,
                        address=item.address,
                        source_provider=item.source_provider,
                        source_ref=item.source_ref,
                        est_cost=item.est_cost,
                        est_cost_currency=item.est_cost_currency or trip.budget_currency,
                        is_outdoor=item.is_outdoor,
                        sort_order=item.sort_order,
                    )
                )
            await session.commit()
            logger.info("itinerary_persisted", trip_id=trip_id, count=len(items))
    except Exception as exc:
        logger.error("itinerary_persist_failed", trip_id=trip_id, error=str(exc))


# ── Coordinate resolution ─────────────────────────────────────────────────────


async def _resolve_coords(trip: Trip) -> tuple[float, float] | None:
    if trip.latitude is not None and trip.longitude is not None:
        return trip.latitude, trip.longitude
    query = f"{trip.destination_city}, {trip.destination_country or ''}"
    point = await geocode(query)
    return (point.lat, point.lng) if point else None


# ── LLM generation ────────────────────────────────────────────────────────────


async def _generate_itinerary(
    trip: Trip,
    style_profile: dict,  # type: ignore[type-arg]
    weather_days: list[WeatherDay],
    attractions: list[Attraction],
    budget_state: dict,  # type: ignore[type-arg]
) -> list[_ItemDraft]:
    prompt = _build_prompt(trip, style_profile, weather_days, attractions, budget_state)
    try:
        llm = _build_llm()
        response = await llm.ainvoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        raw = str(response.content) if hasattr(response, "content") else str(response)
        items = _parse_items(raw, trip)
        if items:
            return items
        logger.warning("itinerary_planner_empty_parse", trip_id=str(trip.id))
    except Exception as exc:
        logger.error("itinerary_planner_llm_error", error=str(exc))

    return _default_itinerary(trip)


def _build_prompt(
    trip: Trip,
    style_profile: dict,  # type: ignore[type-arg]
    weather_days: list[WeatherDay],
    attractions: list[Attraction],
    budget_state: dict,  # type: ignore[type-arg]
) -> str:
    trip_days = (trip.end_date - trip.start_date).days + 1
    budget_str = (
        f"{budget_state.get('total')} {budget_state.get('currency', trip.budget_currency)}"
        if budget_state.get("total")
        else "unspecified"
    )
    country_part = f", {trip.destination_country}" if trip.destination_country else ""

    parts = [
        f"**Trip**: {trip.destination_city}{country_part}",
        f"**Dates**: {trip.start_date} to {trip.end_date} ({trip_days} days)",
        f"**Travelers**: {trip.num_travelers}",
        f"**Budget**: {budget_str}",
    ]

    if style_profile:
        parts += [
            "",
            "**Traveler Style Profile**",
            f"Summary: {style_profile.get('travel_style_summary', '')}",
            f"Tags: {', '.join(style_profile.get('style_tags', []))}",
            f"Accommodation: {style_profile.get('accommodation_preference', '')}",
            f"Activities: {style_profile.get('activity_preference', '')}",
            f"Dining: {style_profile.get('dining_preference', '')}",
            f"Daily rhythm: {style_profile.get('daily_rhythm', '')}",
            f"Budget priority: {style_profile.get('budget_priority', '')}",
        ]

    if weather_days:
        parts += ["", "**Weather Forecast**"]
        for w in weather_days:
            adverse = " ⚠️ ADVERSE" if w.is_adverse else ""
            parts.append(
                f"  {w.date}: {w.condition_label}, "
                f"{w.temp_min_c}–{w.temp_max_c}°C, "
                f"precip {w.precipitation_mm}mm{adverse}"
            )

    if attractions:
        parts += [
            "",
            f"**Real Attractions Near {trip.destination_city}** (use these in the itinerary)",
        ]
        for a in attractions[:25]:  # cap to avoid prompt bloat
            parts.append(
                f"  - {a.name} [{a.kinds}] lat={a.lat:.4f} lng={a.lng:.4f} "
                f"source_provider=overpass source_ref={a.source_ref}"
            )
    else:
        parts.append(
            "\n**Note**: No attraction data available — generate based on destination knowledge."
        )

    parts += [
        "",
        f"Generate a complete itinerary for all {trip_days} day(s). "
        "Include breakfast, key activities, lunch, afternoon activities, and dinner each day. "
        "Prefer indoor venues on adverse weather days. "
        "Output only the JSON array — no explanation.",
    ]

    return "\n".join(parts)


# ── Parsing & validation ──────────────────────────────────────────────────────


def _parse_items(raw: str, trip: Trip) -> list[_ItemDraft]:
    """Extract JSON array from LLM output, validate each item against trip dates."""
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start < 0 or end <= start:
            return []
        data = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    trip_days = (trip.end_date - trip.start_date).days + 1
    valid_dates = {(trip.start_date + timedelta(days=i)).isoformat() for i in range(trip_days)}
    items: list[_ItemDraft] = []
    sort_counters: dict[int, int] = {}

    for raw_item in data:
        if not isinstance(raw_item, dict):
            continue
        # Coerce item_type to valid value
        if raw_item.get("item_type") not in _VALID_ITEM_TYPES:
            raw_item["item_type"] = "activity"
        # Drop items with dates outside the trip window
        if raw_item.get("item_date") not in valid_dates:
            continue
        try:
            item = _ItemDraft(**raw_item)
        except (ValidationError, TypeError):
            continue

        # Reassign sort_order sequentially per day to avoid LLM numbering gaps
        day = item.day_number
        sort_counters[day] = sort_counters.get(day, -1) + 1
        item.sort_order = sort_counters[day]
        items.append(item)

    return items


def _default_itinerary(trip: Trip) -> list[_ItemDraft]:
    """Minimal fallback: one free block per day when LLM is unavailable."""
    trip_days = (trip.end_date - trip.start_date).days + 1
    items: list[_ItemDraft] = []
    for i in range(trip_days):
        day_date = trip.start_date + timedelta(days=i)
        items.append(
            _ItemDraft(
                day_number=i + 1,
                item_date=day_date.isoformat(),
                item_type="free",
                title=f"Explore {trip.destination_city}",
                description="Itinerary generation unavailable — explore at your own pace.",
                is_outdoor=False,
                sort_order=0,
            )
        )
    return items


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_weather_state(weather_days: list[WeatherDay]) -> dict:  # type: ignore[type-arg]
    risk_flags = [w.date.isoformat() for w in weather_days if w.is_adverse]
    return {
        "risk_flags": risk_flags,
        "last_checked": datetime.utcnow().isoformat(),
        "forecast": [
            {
                "date": w.date.isoformat(),
                "condition": w.condition_label,
                "temp_min_c": w.temp_min_c,
                "temp_max_c": w.temp_max_c,
                "is_adverse": w.is_adverse,
            }
            for w in weather_days
        ],
    }


def _parse_time(t: str | None) -> dt_time | None:
    if not t:
        return None
    try:
        parts = t.split(":")
        return dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError, AttributeError):
        return None


def _item_to_dict(item: _ItemDraft) -> dict:  # type: ignore[type-arg]
    return item.model_dump()
