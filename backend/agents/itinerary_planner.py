"""Itinerary Planner agent — fetches real data and generates a day-by-day itinerary via LLM."""

from __future__ import annotations

import asyncio
import json
import math
from datetime import date, datetime, timedelta
from datetime import time as dt_time

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, select

from backend.agents._llm import build_llm
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import ItineraryItem, Trip
from backend.graphs.state import TravelOSState
from backend.tools.geocode import geocode
from backend.tools.places import Attraction, search_attractions
from backend.tools.restaurants import Restaurant, search_restaurants
from backend.tools.weather import WeatherDay, fetch_weather

logger = get_logger(__name__)

_VALID_ITEM_TYPES = frozenset({"activity", "meal", "transport", "lodging", "free"})

# Items per day by pace — injected into the prompt and enforced post-parse
_PACE_ITEMS_PER_DAY: dict[str, int] = {
    "relaxed": 3,  # morning activity, lunch, afternoon activity
    "moderate": 4,  # + dinner
    "packed": 6,  # + early morning + evening activity
}
_DEFAULT_ITEMS_PER_DAY = 4

# Sights with at least this many Wikidata sitelinks are treated as must-see icons and
# forced into the plan (world landmarks have 50–150; obscure local sites have 1–3).
_MUST_SEE_MIN_SITELINKS = 10
_MUST_SEE_CAP = 12

# Kinds that imply an indoor venue (used when creating enforced must-see slots)
_INDOOR_KINDS = frozenset({"museum", "gallery", "aquarium", "theatre", "cinema"})

# Walking tolerance → max metres between consecutive same-day venues (task #4)
_WALKING_TOLERANCE_M: dict[str, int] = {"low": 500, "medium": 2000, "high": 5000}

# Type-based scheduling rules injected into the LLM prompt (task #5)
_MEAL_RULES = "lunch 12:00–14:00 · dinner 19:00–22:00 · nightlife 21:00 or later"
_SCHEDULING_RULES: tuple[tuple[str, str], ...] = (
    ("museum/gallery/aquarium/zoo/theme_park", "09:00–17:00"),
    ("viewpoint/artwork", "morning 08:00–11:00 or late afternoon 16:00–19:00"),
    ("monument/ruins/castle/archaeological_site", "flexible, morning preferred"),
)

_SYSTEM_PROMPT = """You are the Itinerary Planner for TravelOS, an AI travel planning system.
Generate a realistic, day-by-day travel itinerary using the trip data, traveler style profile,
weather forecast, and list of real attractions provided.

Rules:
- Generate the exact number of items per day specified in the user message (varies by pace).
- Use attractions from the provided list whenever possible (exact name, lat, lng, source_ref).
- Schedule indoor activities (museums, galleries) on adverse weather days.
- Respect the traveler's daily rhythm and pace from the style profile.
- Every item must have a valid item_type: activity | meal | transport | lodging | free
- Times use "HH:MM" 24-hour format. Leave null if genuinely unknown.
- est_cost is in the trip's currency. Omit (null) if unknown.
- is_outdoor is true for parks, viewpoints, walking tours, outdoor sites.
- Keep descriptions SHORT (under 30 words each) to avoid hitting output limits.

Respond ONLY with a valid JSON array (no markdown, no explanation):
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


def _cluster_attractions(
    attractions: list[Attraction],
) -> list[tuple[str, str, list[Attraction]]]:
    """Bucket attractions into ~1 km grid cells; return (label, anchor_name, members) triples."""
    if not attractions:
        return []

    _CELL_LAT = 0.009  # ≈ 1 km in latitude
    _CELL_LNG = 0.011  # ≈ 1 km in longitude at mid-latitudes

    cells: dict[tuple[int, int], list[Attraction]] = {}
    for a in attractions:
        key = (int(a.lat / _CELL_LAT), int(a.lng / _CELL_LNG))
        cells.setdefault(key, []).append(a)

    # Largest cluster gets label A, then B, C…
    sorted_groups = sorted(cells.values(), key=len, reverse=True)
    result: list[tuple[str, str, list[Attraction]]] = []
    for i, group in enumerate(sorted_groups):
        label = chr(ord("A") + i) if i < 26 else f"G{i + 1}"
        result.append((label, group[0].name, group))
    return result


def _compass_direction(
    center_lat: float, center_lng: float, point_lat: float, point_lng: float
) -> str:
    """Return an 8-point compass word for the bearing from center to point."""
    dlat = point_lat - center_lat
    dlng = point_lng - center_lng
    if abs(dlat) < 1e-6 and abs(dlng) < 1e-6:
        return "central"
    angle = math.degrees(math.atan2(dlng, dlat))  # 0° = north, 90° = east
    if angle < 0:
        angle += 360
    dirs = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
    return dirs[int((angle + 22.5) / 45) % 8]


def _build_llm() -> BaseChatModel:
    return build_llm("large", temperature=0.7)


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
        weather_days, attractions, restaurants = await asyncio.gather(
            fetch_weather(lat, lng, trip.start_date, trip.end_date),
            # Wide radius so a metro's iconic sights (often >5 km from centre) are in
            # range; search_attractions ranks them prominent-first before truncating.
            search_attractions(lat, lng, radius_m=12000, limit=30),
            search_restaurants(lat, lng, radius_m=2000),
        )
    else:
        logger.warning("itinerary_planner_no_coords", trip_id=trip_id)
        weather_days, attractions, restaurants = [], [], []

    memory_context = state.get("memory_context") or {}
    style_profile = memory_context.get("travel_style_profile", {})
    prefs = memory_context.get("preferences") or {}
    budget_state = state.get("budget_state") or {}
    pace = prefs.get("pace") or "moderate"
    walking_tolerance = prefs.get("walking_tolerance") or "medium"

    items = await _generate_itinerary(
        trip,
        style_profile,
        weather_days,
        attractions,
        restaurants,
        budget_state,
        pace,
        walking_tolerance,
    )

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
    restaurants: list[Restaurant],
    budget_state: dict,  # type: ignore[type-arg]
    pace: str = "moderate",
    walking_tolerance: str = "medium",
) -> list[_ItemDraft]:
    items_per_day = _PACE_ITEMS_PER_DAY.get(pace, _DEFAULT_ITEMS_PER_DAY)
    prompt = _build_prompt(
        trip,
        style_profile,
        weather_days,
        attractions,
        restaurants,
        budget_state,
        items_per_day,
        walking_tolerance,
    )
    try:
        llm = _build_llm()
        response = await llm.ainvoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        raw = str(response.content) if hasattr(response, "content") else str(response)
        items = _parse_items(raw, trip)
        if items:
            items = _assign_real_restaurants(items, restaurants)
            return _enforce_must_see(items, attractions, trip)
        logger.warning("itinerary_planner_empty_parse", trip_id=str(trip.id))
    except Exception as exc:
        logger.error("itinerary_planner_llm_error", error=str(exc))

    return _default_itinerary(trip)


def _build_prompt(
    trip: Trip,
    style_profile: dict,  # type: ignore[type-arg]
    weather_days: list[WeatherDay],
    attractions: list[Attraction],
    restaurants: list[Restaurant],
    budget_state: dict,  # type: ignore[type-arg]
    items_per_day: int = _DEFAULT_ITEMS_PER_DAY,
    walking_tolerance: str = "medium",
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
        # City center for compass bearings; fall back to mean of attractions
        if trip.latitude is not None and trip.longitude is not None:
            center_lat, center_lng = float(trip.latitude), float(trip.longitude)
        else:
            center_lat = sum(a.lat for a in attractions) / len(attractions)
            center_lng = sum(a.lng for a in attractions) / len(attractions)

        clusters = _cluster_attractions(attractions)

        # MUST-SEE: the most world-famous sights (by Wikidata sitelink count) take
        # absolute priority — list them explicitly and require every one be scheduled.
        must_see = [
            a for a in attractions if a.prominence >= _MUST_SEE_MIN_SITELINKS or a.is_heritage
        ][:_MUST_SEE_CAP]
        if must_see:
            parts += [
                "",
                "**MUST-SEE landmarks** (most famous first) — the area's iconic sights."
                " Schedule as many of these as the days allow, always preferring them over"
                " any other venue and spreading them across the days:",
            ]
            for a in must_see:
                parts.append(f"  • {a.name} [{a.kinds}] source_ref={a.source_ref}")

        any_major = any(a.is_major for a in attractions)
        legend = " — ★ marks a major / well-known sight; prefer these" if any_major else ""
        parts += [
            "",
            f"**Real Attractions Near {trip.destination_city}**"
            " (grouped by walking zone — prefer same-day activities within one group)" + legend,
        ]
        for label, anchor, members in clusters[:6]:  # cap at 6 clusters
            clat = sum(a.lat for a in members) / len(members)
            clng = sum(a.lng for a in members) / len(members)
            direction = _compass_direction(center_lat, center_lng, clat, clng)
            parts.append(f"  Group {label} — {direction}, near {anchor}")
            # Most-prominent (★, high composite score) sights first so they survive the cap.
            ranked = sorted(members, key=lambda a: (not a.is_major, -a.score, a.name))
            for a in ranked[:6]:  # cap at 6 per cluster
                star = " ★" if a.is_major else ""
                hours_str = f" hours={a.opening_hours}" if a.opening_hours else ""
                parts.append(
                    f"    · {a.name}{star} [{a.kinds}] lat={a.lat:.4f} lng={a.lng:.4f}"
                    f" source_ref={a.source_ref}{hours_str}"
                )
    else:
        parts.append(
            "\n**Note**: No attraction data available — generate based on destination knowledge."
        )

    # Walking constraint (task #4)
    tolerance_m = _WALKING_TOLERANCE_M.get(walking_tolerance, 2000)
    parts += [
        "",
        f"**Walking Constraint**: Keep consecutive same-day venues within {tolerance_m} m."
        " Assign activities from the same cluster to the same day where possible.",
    ]

    # Time-of-day scheduling guidelines (task #5)
    parts += ["", "**Scheduling Guidelines**", f"  Meals: {_MEAL_RULES}"]
    for kinds_str, window in _SCHEDULING_RULES:
        parts.append(f"  {kinds_str} → {window}")

    # Prominence + variety priorities (task #23)
    parts += [
        "",
        "**Selection priorities** (apply in order):",
        "  1. Prominence — favour iconic, well-known sights over obscure ones. A great"
        " day is anchored by a famous landmark, not filler; include the city's signature"
        " attractions even if slightly farther.",
        "  2. Variety — at most 2 venues of the same kind per day (e.g. ≤2 museums)."
        " Mix indoor and outdoor and vary the experience across the day.",
        "  3. Proximity — only then group the day's picks within one walking zone.",
        "",
        "**Example of one well-balanced day** (follow this PATTERN, not these names):",
        "  09:00 a major museum or landmark (indoor) · 12:30 lunch at a local restaurant"
        " · 15:00 a contrasting OUTDOOR sight nearby — a park or viewpoint · 19:30 dinner."
        "  → one museum, an indoor+outdoor mix, no same-type repeats.",
    ]

    if items_per_day <= 3:
        structure = "morning activity, lunch (meal), afternoon activity"
    elif items_per_day == 4:
        structure = "morning activity, lunch (meal), afternoon activity, dinner (meal)"
    else:
        structure = (
            "early morning activity, morning activity, lunch (meal), "
            "afternoon activity, dinner (meal), evening activity"
        )

    parts += [
        "",
        f"Generate exactly {items_per_day} items per day for all {trip_days} day(s): "
        f"{structure}. "
        "Keep descriptions under 30 words. "
        "Prefer indoor venues on adverse weather days. "
        "Output only the JSON array — no markdown fences, no explanation.",
    ]

    return "\n".join(parts)


# ── Must-see enforcement ──────────────────────────────────────────────────────


def _enforce_must_see(
    items: list[_ItemDraft],
    attractions: list[Attraction],
    trip: Trip,
) -> list[_ItemDraft]:
    """Swap top must-see attractions into the plan if the LLM missed any.

    Leaves at least 2 non-forced activity slots per day so variety is preserved.
    """
    must_see = [a for a in attractions if a.prominence >= _MUST_SEE_MIN_SITELINKS or a.is_heritage][
        :_MUST_SEE_CAP
    ]
    if not must_see:
        return items

    scheduled_refs: set[str] = {i.source_ref for i in items if i.source_ref}
    scheduled_names_lower: set[str] = {i.title.lower() for i in items}
    must_see_refs: set[str] = {a.source_ref for a in must_see}
    must_see_names_lower: set[str] = {a.name.lower() for a in must_see}

    missing = [
        a
        for a in must_see
        if a.source_ref not in scheduled_refs and a.name.lower() not in scheduled_names_lower
    ]
    if not missing:
        return items

    # Activity slots eligible for replacement: not a meal/transport, not already a must-see
    replaceable = [
        i
        for i in items
        if i.item_type == "activity"
        and (i.source_ref or "") not in must_see_refs
        and i.title.lower() not in must_see_names_lower
    ]
    # LLM-invented items (no coordinates) have lower value and are replaced first
    replaceable.sort(key=lambda i: (i.latitude is not None, i.day_number, i.sort_order))

    # Cap swaps so at least 2 non-forced activity slots remain per day for variety
    trip_days = (trip.end_date - trip.start_date).days + 1
    activity_count = sum(1 for i in items if i.item_type == "activity")
    max_swaps = max(0, activity_count - trip_days * 2)
    if max_swaps == 0:
        return items

    result = list(items)
    swaps = 0
    for attraction in missing:
        if swaps >= max_swaps or not replaceable:
            break
        slot = replaceable.pop(0)
        idx = result.index(slot)
        is_outdoor = not any(k in attraction.kinds for k in _INDOOR_KINDS)
        result[idx] = _ItemDraft(
            day_number=slot.day_number,
            item_date=slot.item_date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            item_type="activity",
            title=attraction.name,
            description=attraction.kinds,
            latitude=attraction.lat,
            longitude=attraction.lng,
            source_provider="overpass",
            source_ref=attraction.source_ref,
            is_outdoor=is_outdoor,
            sort_order=slot.sort_order,
        )
        swaps += 1
        logger.info(
            "must_see_enforced",
            attraction=attraction.name,
            replaced=slot.title,
            day=slot.day_number,
        )

    if swaps:
        logger.info("must_see_swaps_applied", count=swaps, trip_id=str(trip.id))
    return result


# ── Restaurant assignment ─────────────────────────────────────────────────────


def _assign_real_restaurants(
    items: list[_ItemDraft], restaurants: list[Restaurant]
) -> list[_ItemDraft]:
    """Replace LLM meal placeholders with real restaurants, cycling through the fetched list."""
    if not restaurants:
        return items
    idx = 0
    result: list[_ItemDraft] = []
    for item in items:
        if item.item_type == "meal":
            r = restaurants[idx % len(restaurants)]
            idx += 1
            result.append(
                _ItemDraft(
                    day_number=item.day_number,
                    item_date=item.item_date,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    item_type="meal",
                    title=r.name,
                    description=r.categories[0] if r.categories else None,
                    latitude=r.lat,
                    longitude=r.lng,
                    address=r.address,
                    source_provider=r.source_provider,
                    source_ref=r.source_ref,
                    est_cost=item.est_cost,
                    est_cost_currency=item.est_cost_currency,
                    is_outdoor=False,
                    sort_order=item.sort_order,
                )
            )
        else:
            result.append(item)
    return result


# ── Parsing & validation ──────────────────────────────────────────────────────


def _parse_items(raw: str, trip: Trip) -> list[_ItemDraft]:
    """Extract JSON array from LLM output, validate each item against trip dates."""
    try:
        start = raw.find("[")
        if start < 0:
            return []
        end = raw.rfind("]") + 1
        if end <= start:
            # Truncated response (finish_reason=length) — recover complete objects up to last }
            last_obj = raw.rfind("}")
            if last_obj < start:
                return []
            end = last_obj + 1
            raw = raw[start:end] + "]"
        else:
            raw = raw[start:end]
        data = json.loads(raw)
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
