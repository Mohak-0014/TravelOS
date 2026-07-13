"""Itinerary Planner agent — fetches real data and generates a day-by-day itinerary via LLM."""

from __future__ import annotations

import asyncio
import json
import math
import re
from collections import Counter
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
from backend.tools.currency import destination_currency as _local_currency
from backend.tools.destination_profile import DestinationProfile, compute_destination_profile
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
# Signature-category venues (a Goa beach, a Manali trek) qualify as must-see at a lower
# sitelink bar — beaches rarely reach world-landmark counts yet ARE the destination.
_SIGNATURE_MIN_SITELINKS = 5
# At most this many must-sees per category OUTSIDE the destination's signature
# categories, so the forced list can't be 12 museums in a beach town. Signature
# categories are uncapped — Delhi's monuments (India Gate, Red Fort, Qutub Minar,
# Humayun's Tomb…) must all stay eligible.
_MUST_SEE_OFFSIG_CAT_CAP = 3

# Travel-DNA tag/interest → experience categories the traveler favours.
_TAG_CATEGORY_AFFINITY: dict[str, frozenset[str]] = {
    "adventure": frozenset({"water_sport", "adventure"}),
    "sports": frozenset({"water_sport", "adventure"}),
    "nature": frozenset({"nature", "beach", "viewpoint"}),
    "relaxation": frozenset({"beach", "nature"}),
    "culture": frozenset({"museum_gallery", "heritage_monument", "religious"}),
    "history": frozenset({"heritage_monument", "museum_gallery"}),
    "art": frozenset({"museum_gallery"}),
    "nightlife": frozenset({"entertainment"}),
    "family_friendly": frozenset({"entertainment"}),
}
_SIGNATURE_BOOST = 0.20  # score bonus for the destination's signature categories
_DNA_BOOST = 0.15  # score bonus for the traveler's DNA-favoured categories
_CORE_BOOST = 0.25  # extra bonus for the categories that define the destination type

# The categories that ARE the destination: what a traveler goes to a beach/nature place
# for. These get the strongest boost, a fame-free must-see path (famous beaches rarely
# have world-landmark sitelink counts), and first pick as composition-swap candidates.
_CORE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "beach": ("beach", "water_sport"),
    "nature": ("nature", "adventure"),
}
_MUST_SEE_CORE_CAP = 3  # max fame-free core venues forced into the must-see list

# Museums/galleries may fill at most this share of activity slots in a beach/nature
# destination (deterministic backstop against museum-heavy LLM output).
_MAX_MUSEUM_SHARE = 0.34

# Variety backstop: max same-kind activities per TRIP. The prompt's "≤2 per day" rule
# can't stop 3 spice farms across 3 days, and the must-see/composition passes can even
# introduce repeats (their candidates are all top-scored venues of one kind — 4 summits
# in 4 days). Signature/core kinds get one extra slot; a fourth is always a repeat.
_VARIETY_KIND_CAP = 2
_VARIETY_KIND_CAP_SIG = 3
# Within the fame-free core must-see picks, at most this many share one fine kind — the
# forced list must read "a peak, a waterfall, a lake", not "three peaks".
_MUST_SEE_CORE_KIND_CAP = 2
# Title words too generic to link two venues into one variety group.
_VARIETY_TITLE_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "of",
        "at",
        "in",
        "near",
        "old",
        "new",
        "great",
        "grand",
        "little",
        "upper",
        "lower",
        "north",
        "south",
        "east",
        "west",
        "national",
        "royal",
        "sacred",
        "holy",
        "saint",
        "santa",
        "san",
    }
)

# Categories that are outdoor by definition.
_OUTDOOR_CATEGORIES = frozenset({"beach", "water_sport", "adventure", "nature", "viewpoint"})

# Kinds that imply an indoor venue (used when creating enforced must-see slots)
_INDOOR_KINDS = frozenset({"museum", "gallery", "aquarium", "theatre", "cinema"})

# Kinds that are always outdoor/active — never schedule these on adverse weather days
_OUTDOOR_ACTIVITY_KINDS = frozenset(
    {
        "surfing",
        "diving",
        "scuba_diving",
        "snorkeling",
        "swimming",
        "water_skiing",
        "kitesurfing",
        "windsurfing",
        "rafting",
        "canoeing",
        "kayaking",
        "paragliding",
        "climbing",
        "bungee_jumping",
        "canyoning",
        "cycling",
        "horse_riding",
        "sailing",
        "water_park",
        "marina",
        "sports_centre",
        "beach_resort",
        "swimming_area",
        "dive_centre",
        "surf_school",
    }
)

# Walking tolerance → max metres between consecutive same-day venues (task #4)
_WALKING_TOLERANCE_M: dict[str, int] = {"low": 500, "medium": 2000, "high": 5000}

# Attraction fetch: metro radius first; if the pool comes back sparse the destination is
# a region/state (e.g. "Goa" geocodes to an inland centroid ~20 km from the coast) or a
# small town — refetch once at region scale so the signature sights (beaches, treks)
# enter the pool. Sparse implies not-dense, so the wide Overpass query stays cheap.
# The region radius is sized from the destination's own Nominatim bounding box (Goa the
# state spans ~60 km half-diagonal — a fixed 40 km missed Baga/Calangute in North Goa),
# clamped so a country-level bbox can't produce an absurd query.
_ATTRACTION_LIMIT = 30
_METRO_RADIUS_M = 12000
_REGION_RADIUS_M = 40000  # floor / fallback when no bbox is available
_REGION_RADIUS_MAX_M = 75000

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
- est_cost MUST be a realistic price in the DESTINATION'S LOCAL currency (stated in the user
  message). ALWAYS populate est_cost_currency with that ISO-4217 code. NEVER use the
  traveller's home currency for est_cost — e.g. for a Bali trip use IDR amounts, NOT INR.
  Realistic ranges by currency:
    IDR: temple/museum 15000–150000 · meal 30000–120000 · activity 100000–600000
    JPY: shrine/museum 500–2000 · meal 800–3000 · activity 2000–10000
    THB: temple 100–500 · meal 100–400 · activity 500–3000
    USD: museum 5–30 · meal 10–30 · activity 20–100
    EUR: museum 5–20 · meal 10–25 · activity 15–80
- Omit est_cost (null) only when the cost is genuinely unknown.
- is_outdoor is true for parks, viewpoints, walking tours, outdoor sites, beaches, AND all
  water/adventure sports.
- Water/adventure sports (surfing, diving, snorkeling, rafting, kayaking, paragliding, etc.)
  are valid activity items — use them when the destination is known for them. Mark is_outdoor: true.
- Avoid scheduling outdoor adventure sports on adverse weather days — prefer indoor alternatives.
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
    "est_cost": 50000,
    "est_cost_currency": "IDR",
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
    region_scale = False

    # Fetch weather and attractions in parallel — both degrade gracefully to []
    if coords:
        lat, lng = coords
        weather_days, attractions, restaurants = await asyncio.gather(
            fetch_weather(lat, lng, trip.start_date, trip.end_date),
            # Wide radius so a metro's iconic sights (often >5 km from centre) are in
            # range; search_attractions ranks them prominent-first before truncating.
            search_attractions(lat, lng, radius_m=_METRO_RADIUS_M, limit=_ATTRACTION_LIMIT),
            search_restaurants(lat, lng, radius_m=5000),
        )
        if len(attractions) < _ATTRACTION_LIMIT:
            region_radius = await _region_radius_m(trip)
            logger.info(
                "itinerary_sparse_pool_widening",
                trip_id=trip_id,
                metro_count=len(attractions),
                region_radius_m=region_radius,
            )
            wide = await search_attractions(
                lat, lng, radius_m=region_radius, limit=_ATTRACTION_LIMIT
            )
            if len(wide) > len(attractions):
                attractions = wide
                region_scale = True
    else:
        logger.warning("itinerary_planner_no_coords", trip_id=trip_id)
        weather_days, attractions, restaurants = [], [], []

    memory_context = state.get("memory_context") or {}
    style_profile = memory_context.get("travel_style_profile", {})
    prefs = memory_context.get("preferences") or {}
    budget_state = state.get("budget_state") or {}
    pace = prefs.get("pace") or "moderate"
    walking_tolerance = prefs.get("walking_tolerance") or "medium"

    local_currency = _local_currency(trip.destination_city, trip.destination_country)

    # What is this place famous for, and what does this traveler favour? Both reorder
    # the candidate list so the LLM's menu leads with destination-fit venues.
    dest_profile = compute_destination_profile(attractions, region_scale=region_scale)
    dna_categories = _dna_categories(style_profile, prefs)
    core_categories = set(_CORE_CATEGORIES.get(dest_profile.type, ()))
    attractions = _boost_attractions(
        attractions, set(dest_profile.signature_categories), dna_categories, core_categories
    )
    logger.info(
        "itinerary_destination_profile",
        trip_id=trip_id,
        dest_type=dest_profile.type,
        signature=dest_profile.signature_categories,
        dna_categories=sorted(dna_categories),
    )

    items = await _generate_itinerary(
        trip,
        style_profile,
        weather_days,
        attractions,
        restaurants,
        budget_state,
        pace,
        walking_tolerance,
        local_currency,
        profile=dest_profile,
        dna_categories=dna_categories,
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
                        est_cost_currency=item.est_cost_currency,
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


async def _region_radius_m(trip: Trip) -> int:
    """Region-scale fetch radius sized to the destination's own extent.

    Trips only store a point, so re-geocode for the Nominatim bounding box (the planner
    path is uncached — always fresh). Degrades to the fixed fallback on any failure.
    """
    try:
        point = await geocode(f"{trip.destination_city}, {trip.destination_country or ''}")
    except Exception as exc:
        logger.warning("region_radius_geocode_failed", trip_id=str(trip.id), error=str(exc))
        point = None
    bbox_radius = point.bbox_radius_m if point is not None else None
    if not bbox_radius:
        return _REGION_RADIUS_M
    return int(min(max(bbox_radius, _REGION_RADIUS_M), _REGION_RADIUS_MAX_M))


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
    local_currency: str = "USD",
    profile: DestinationProfile | None = None,
    dna_categories: set[str] | None = None,
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
        local_currency,
        profile=profile,
        dna_categories=dna_categories,
    )
    try:
        llm = _build_llm()
        response = await llm.ainvoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        raw = str(response.content) if hasattr(response, "content") else str(response)
        items = _parse_items(raw, trip)
        if items:
            # LLM was told to use local_currency amounts but often ignores this and
            # emits the traveler's budget currency (e.g. INR for a Bali trip) or omits
            # the field. Override unconditionally so e.g. IDR 30000 isn't treated as
            # INR 30000 by the budget optimizer.
            for item in items:
                if item.est_cost is not None:
                    item.est_cost_currency = local_currency
            items = _assign_real_restaurants(items, restaurants)
            signature = set(profile.signature_categories) if profile else set()
            core = set(_CORE_CATEGORIES.get(profile.type, ())) if profile else set()
            items = _enforce_must_see(
                items,
                attractions,
                trip,
                signature_cats=signature,
                dna_cats=dna_categories,
                core_cats=core,
            )
            items = _enforce_composition(items, attractions, profile, dna_categories)
            items = _enforce_variety(items, attractions, trip, signature, core)
            return _normalize_outdoor(items, attractions)
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
    local_currency: str = "USD",
    profile: DestinationProfile | None = None,
    dna_categories: set[str] | None = None,
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
        f"**Budget**: {budget_str} (traveler's home currency — DO NOT use this currency"
        " for est_cost)",
        f"**Local currency for est_cost**: {local_currency}",
        f"  → Use ONLY {local_currency} amounts for every est_cost field.",
        f'  → Set est_cost_currency to "{local_currency}" on every item that has a cost.',
        "  → Example correct entry:"
        f' {{"est_cost": 50000, "est_cost_currency": "{local_currency}"}}',
        "  → WRONG (never do this):"
        f' {{"est_cost": 500, "est_cost_currency": "{trip.budget_currency}"}}',
    ]

    if profile is not None and profile.signature_categories:
        sig = ", ".join(c.replace("_", " ") for c in profile.signature_categories)
        parts += [
            "",
            f"**Destination Character**: a {profile.type} destination — famous for: {sig}.",
            "  → Anchor most days around these signature experiences. Do NOT fill days"
            " with generic museums or minor cultural sites unless they are landmarks in"
            " their own right.",
        ]
        if profile.type in {"beach", "nature"} and "museum_gallery" not in (
            dna_categories or set()
        ):
            preferred = (
                "beaches, water sports, viewpoints and coastal experiences"
                if profile.type == "beach"
                else "treks, viewpoints, waterfalls, nature and adventure activities"
            )
            parts.append(
                "  → HARD LIMIT: at most 2 museum/gallery visits across the WHOLE trip."
                f" Prefer {preferred}."
            )

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

        # MUST-SEE: the most famous sights take absolute priority — list them explicitly
        # and require every one be scheduled. Category-capped so a beach town's list
        # isn't 12 museums, and signature venues qualify at a lower fame bar.
        signature = set(profile.signature_categories) if profile else set()
        core = set(_CORE_CATEGORIES.get(profile.type, ())) if profile else set()
        must_see = _select_must_see(attractions, signature, core)
        if must_see:
            parts += [
                "",
                "**MUST-SEE landmarks** (most famous first) — the area's iconic sights."
                " Schedule as many of these as the days allow, always preferring them over"
                " any other venue and spreading them across the days:",
            ]
            for a in must_see:
                parts.append(f"  • {a.name} [{_kind_label(a)}] source_ref={a.source_ref}")

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
            # Most-prominent (★, high composite score) sights first so they survive the
            # cap — but kind-diverse, so a peak-heavy cluster's menu isn't all peaks.
            ranked = sorted(members, key=lambda a: (not a.is_major, -a.score, a.name))
            for a in _diverse_by_kind(ranked, 6):  # cap at 6 per cluster
                star = " ★" if a.is_major else ""
                hours_str = f" hours={a.opening_hours}" if a.opening_hours else ""
                parts.append(
                    f"    · {a.name}{star} [{_kind_label(a)}] lat={a.lat:.4f} lng={a.lng:.4f}"
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

    # Destination fit + prominence + variety priorities
    parts += [
        "",
        "**Selection priorities** (apply in order):",
        "  1. Destination fit — match the mix of activity types to what THIS place is"
        " famous for (see Destination Character) and to the traveler's style. A beach"
        " destination's days are anchored by beaches and water sports; a heritage city's"
        " by its monuments and forts; a hill station's by treks and viewpoints. Museums"
        " are filler unless the destination or traveler is culture-focused.",
        "  2. Prominence — within the right type, favour iconic, well-known sights over"
        " obscure ones. A great day is anchored by a famous landmark, not filler; include"
        " the destination's signature attractions even if slightly farther.",
        "  3. Variety — at most 2 venues of the same kind per day (e.g. ≤2 museums)."
        " Mix indoor and outdoor and vary the experience across the day.",
        "  4. Proximity — only then group the day's picks within one walking zone.",
        "",
        "**Example of one well-balanced day** (follow this PATTERN, not these names):",
        "  09:00 a signature sight matching the destination (a famous beach, fort or trek)"
        " · 12:30 lunch at a local restaurant · 15:00 a contrasting experience — a"
        " viewpoint, water sport or one major museum · 19:30 dinner."
        "  → anchored by what the place is known for, indoor+outdoor mix, no same-type"
        " repeats.",
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


# ── Destination-fit helpers ───────────────────────────────────────────────────


def _diverse_by_kind(ranked: list[Attraction], n: int) -> list[Attraction]:
    """Top-``n`` of an already-ranked list, at most 2 per fine kind; backfill by rank."""
    picked: list[Attraction] = []
    counts: Counter[str] = Counter()
    for a in ranked:
        if counts[a.kinds] < 2:
            picked.append(a)
            counts[a.kinds] += 1
        if len(picked) >= n:
            return picked
    for a in ranked:
        if len(picked) >= n:
            break
        if a not in picked:
            picked.append(a)
    return picked


def _kind_label(a: Attraction) -> str:
    """Prompt label combining the normalized category with the raw OSM kind."""
    if a.category != "other" and a.category != a.kinds:
        return f"{a.category}: {a.kinds}"
    return a.kinds


def _dna_categories(
    style_profile: dict,  # type: ignore[type-arg]
    prefs: dict,  # type: ignore[type-arg]
) -> set[str]:
    """Experience categories favoured by the traveler's DNA (style tags + interests)."""
    terms = [str(t).lower() for t in (style_profile.get("style_tags") or [])]
    terms += [str(i).lower() for i in (prefs.get("interests") or [])]
    cats: set[str] = set()
    for term in terms:
        cats |= _TAG_CATEGORY_AFFINITY.get(term, frozenset())
    return cats


def _boost_attractions(
    attractions: list[Attraction],
    signature_cats: set[str],
    dna_cats: set[str],
    core_cats: set[str] | None = None,
) -> list[Attraction]:
    """Re-rank candidates so destination-signature and DNA-favoured venues lead the list."""
    for a in attractions:
        if a.category in signature_cats:
            a.score += _SIGNATURE_BOOST
        if a.category in dna_cats:
            a.score += _DNA_BOOST
        if core_cats and a.category in core_cats:
            a.score += _CORE_BOOST
    return sorted(attractions, key=lambda a: (-a.score, -a.prominence, a.name))


def _draft_from_attraction(slot: _ItemDraft, attraction: Attraction) -> _ItemDraft:
    """A new draft occupying ``slot``'s schedule position but pointing at ``attraction``."""
    return _ItemDraft(
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
        is_outdoor=_attraction_is_outdoor(attraction),
        sort_order=slot.sort_order,
    )


def _attraction_is_outdoor(a: Attraction) -> bool:
    if a.category in _OUTDOOR_CATEGORIES:
        return True
    return any(k in a.kinds for k in _OUTDOOR_ACTIVITY_KINDS) or not any(
        k in a.kinds for k in _INDOOR_KINDS
    )


def _select_must_see(
    attractions: list[Attraction],
    signature_cats: set[str],
    core_cats: set[str] | None = None,
) -> list[Attraction]:
    """Pick the must-see list: world icons plus the destination's signature venues.

    Signature-category venues qualify at a lower fame bar, and core venues (the beaches
    of a beach destination) need no fame at all — a Goa beach with 2 sitelinks IS the
    trip. Non-signature categories are capped so the forced list can't be monopolized
    by one venue type (e.g. 12 museums in a beach town); fame-free core entries are
    capped too so the list isn't all beaches.
    """
    core = core_cats or set()
    eligible = [
        a
        for a in attractions
        if a.prominence >= _MUST_SEE_MIN_SITELINKS
        or a.is_heritage
        or (
            a.category in signature_cats
            and (a.prominence >= _SIGNATURE_MIN_SITELINKS or a.has_wikivoyage)
        )
        or a.category in core
    ]
    out: list[Attraction] = []
    cat_counts: Counter[str] = Counter()
    core_kind_counts: Counter[str] = Counter()
    for a in eligible:  # already fame/boost-ordered
        if a.category in core:
            cap = _MUST_SEE_CORE_CAP
            # Diversify WITHIN the core picks: without this, a nature destination's
            # fame-free list is the three top-scored peaks — all the same experience.
            if core_kind_counts[a.kinds] >= _MUST_SEE_CORE_KIND_CAP:
                continue
        elif a.category in signature_cats:
            cap = _MUST_SEE_CAP  # effectively uncapped
        else:
            cap = _MUST_SEE_OFFSIG_CAT_CAP
        if cat_counts[a.category] >= cap:
            continue
        out.append(a)
        cat_counts[a.category] += 1
        if a.category in core:
            core_kind_counts[a.kinds] += 1
        if len(out) >= _MUST_SEE_CAP:
            break
    return out


# ── Must-see enforcement ──────────────────────────────────────────────────────


def _enforce_must_see(
    items: list[_ItemDraft],
    attractions: list[Attraction],
    trip: Trip,
    signature_cats: set[str] | None = None,
    dna_cats: set[str] | None = None,
    core_cats: set[str] | None = None,
) -> list[_ItemDraft]:
    """Swap top must-see attractions into the plan if the LLM missed any.

    Leaves at least 1 non-forced activity slot per day so variety is preserved, and
    never replaces items in the destination's signature or the traveler's DNA-favoured
    categories (a surf lesson must not give way to a fourth church).
    """
    signature = signature_cats or set()
    protected_cats = signature | (dna_cats or set())
    must_see = _select_must_see(attractions, signature, core_cats)
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

    by_ref = {a.source_ref: a for a in attractions}

    def _slot_category(item: _ItemDraft) -> str | None:
        a = by_ref.get(item.source_ref or "")
        return a.category if a is not None else None

    # Activity slots eligible for replacement: not a meal/transport, not already a
    # must-see, not in a protected (signature/DNA) category
    replaceable = [
        i
        for i in items
        if i.item_type == "activity"
        and (i.source_ref or "") not in must_see_refs
        and i.title.lower() not in must_see_names_lower
    ]
    # LLM-invented items (no coordinates) have lower value and are replaced first
    replaceable.sort(key=lambda i: (i.latitude is not None, i.day_number, i.sort_order))

    # Cap swaps so at least 1 non-forced activity slot remains per day for variety.
    # (A stricter 2-per-day floor made enforcement a no-op for the common 4-day
    # moderate-pace trip: 8 activities − 8 floor = 0 swaps.)
    trip_days = (trip.end_date - trip.start_date).days + 1
    activity_count = sum(1 for i in items if i.item_type == "activity")
    max_swaps = max(0, activity_count - trip_days)
    if max_swaps == 0:
        return items

    result = list(items)
    swaps = 0
    for attraction in missing:
        if swaps >= max_swaps or not replaceable:
            break
        # A protected (signature/DNA-favoured) slot may only be upgraded like-for-like:
        # an obscure monument can yield to India Gate, but a surf lesson never yields
        # to a museum.
        slot = next(
            (
                s
                for s in replaceable
                if _slot_category(s) not in protected_cats
                or _slot_category(s) == attraction.category
            ),
            None,
        )
        if slot is None:
            continue
        replaceable.remove(slot)
        idx = result.index(slot)
        result[idx] = _draft_from_attraction(slot, attraction)
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


# ── Composition backstop ──────────────────────────────────────────────────────


def _enforce_composition(
    items: list[_ItemDraft],
    attractions: list[Attraction],
    profile: DestinationProfile | None,
    dna_categories: set[str] | None,
) -> list[_ItemDraft]:
    """Deterministic backstop against museum-heavy plans in beach/nature destinations.

    If museums/galleries exceed _MAX_MUSEUM_SHARE of activity slots, the least famous
    ones are swapped for the best unscheduled core venues (beaches, treks, water
    sports). Applies regardless of travel DNA — the style agent tags almost every
    traveler with "culture", and even a museum lover in Goa keeps a third of their
    slots as museums.
    """
    if profile is None or profile.type not in {"beach", "nature"}:
        return items

    by_ref = {a.source_ref: a for a in attractions}

    def _item_category(item: _ItemDraft) -> str | None:
        a = by_ref.get(item.source_ref or "")
        if a is not None:
            return a.category
        title = item.title.lower()
        if "museum" in title or "gallery" in title:
            return "museum_gallery"
        return None

    activities = [i for i in items if i.item_type == "activity"]
    museums = [i for i in activities if _item_category(i) == "museum_gallery"]
    max_museums = max(1, int(len(activities) * _MAX_MUSEUM_SHARE))
    excess = len(museums) - max_museums
    if excess <= 0:
        return items

    scheduled_refs = {i.source_ref for i in items if i.source_ref}
    scheduled_names = {i.title.lower() for i in items}

    def _unscheduled(categories: set[str]) -> list[Attraction]:
        return [
            a
            for a in attractions  # already boost-ordered best-first
            if a.category in categories
            and a.category != "museum_gallery"
            and a.source_ref not in scheduled_refs
            and a.name.lower() not in scheduled_names
        ]

    # Core venues first — a Goa museum should become a beach, not another church.
    candidates = _unscheduled(set(_CORE_CATEGORIES.get(profile.type, ())))
    candidates += [
        a for a in _unscheduled(set(profile.signature_categories)) if a not in candidates
    ]
    if not candidates:
        return items

    # Replace the least famous museums first, keeping any true icon.
    def _fame(item: _ItemDraft) -> int:
        a = by_ref.get(item.source_ref or "")
        return a.prominence if a is not None else -1

    museums.sort(key=_fame)
    result = list(items)
    swapped = 0
    for slot in museums:
        if swapped >= excess or not candidates:
            break
        attraction = candidates.pop(0)
        idx = result.index(slot)
        result[idx] = _draft_from_attraction(slot, attraction)
        swapped += 1
        logger.info(
            "composition_enforced",
            replaced=slot.title,
            with_venue=attraction.name,
            day=slot.day_number,
        )
    return result


# ── Variety backstop ──────────────────────────────────────────────────────────


def _title_tokens(title: str, extra_stopwords: set[str]) -> set[str]:
    """Significant lowercase words of a venue title, for duplicate-experience detection."""
    return {
        t
        for t in re.split(r"[^a-z]+", title.lower())
        if len(t) >= 4 and t not in _VARIETY_TITLE_STOPWORDS and t not in extra_stopwords
    }


def _enforce_variety(
    items: list[_ItemDraft],
    attractions: list[Attraction],
    trip: Trip,
    signature_cats: set[str] | None = None,
    core_cats: set[str] | None = None,
) -> list[_ItemDraft]:
    """Deterministic per-trip cap on repeated experiences.

    The prompt's "≤2 same-kind venues per day" is per-day and advisory only — it can't
    stop 3 spice farms across a trip, and the must-see/composition passes themselves
    stack top-scored venues of one kind (4 summits in 4 days). Activities are grouped
    as "the same experience" when they share a fine-grained OSM kind OR a significant
    title word ("Hakuna Matata Spice Farm" / "Jambo Spice Farm" — different tags, same
    outing). Each group keeps at most one venue per day and _VARIETY_KIND_CAP per trip
    (+1 for signature/core kinds); the least famous excess is swapped for the best
    unscheduled venue of a different, under-represented kind.
    """
    protected = (signature_cats or set()) | (core_cats or set())
    by_ref = {a.source_ref: a for a in attractions}
    city_tokens = {t for t in re.split(r"[^a-z]+", (trip.destination_city or "").lower()) if t}

    act_idx = [i for i, it in enumerate(items) if it.item_type == "activity"]
    if len(act_idx) < 2:
        return items

    kinds: list[str] = []
    tokens: list[set[str]] = []
    for i in act_idx:
        a = by_ref.get(items[i].source_ref or "")
        kinds.append(a.kinds if a is not None else "")
        tokens.append(_title_tokens(items[i].title, city_tokens))

    # Union-find over activity slots: same kind or shared title word → one group.
    parent = list(range(len(act_idx)))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(act_idx)):
        for j in range(i + 1, len(act_idx)):
            if (kinds[i] and kinds[i] == kinds[j]) or (tokens[i] & tokens[j]):
                parent[_find(j)] = _find(i)

    groups: dict[int, list[int]] = {}
    for pos in range(len(act_idx)):
        groups.setdefault(_find(pos), []).append(pos)

    def _fame(pos: int) -> int:
        a = by_ref.get(items[act_idx[pos]].source_ref or "")
        return a.prominence if a is not None else -1

    def _category(pos: int) -> str | None:
        a = by_ref.get(items[act_idx[pos]].source_ref or "")
        return a.category if a is not None else None

    # Current per-kind totals, updated as replacements are chosen so a swap can't
    # itself create a new over-represented kind.
    kind_totals: Counter[str] = Counter(k for k in kinds if k)

    def _kind_cap(category: str | None) -> int:
        return _VARIETY_KIND_CAP_SIG if category in protected else _VARIETY_KIND_CAP

    scheduled_refs = {it.source_ref for it in items if it.source_ref}
    scheduled_names = {it.title.lower() for it in items}
    candidates = [
        a
        for a in attractions  # already boost-ordered best-first
        if a.category != "museum_gallery"  # never fight the museum-share backstop
        and a.source_ref not in scheduled_refs
        and a.name.lower() not in scheduled_names
    ]

    result = list(items)
    swapped = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        cap = max(_kind_cap(_category(pos)) for pos in members)
        # Keep the most famous; within the group also at most one venue per day.
        keep: list[int] = []
        used_days: set[int] = set()
        excess: list[int] = []
        for pos in sorted(members, key=lambda p: -_fame(p)):
            day = items[act_idx[pos]].day_number
            if len(keep) < cap and day not in used_days:
                keep.append(pos)
                used_days.add(day)
            else:
                excess.append(pos)
        keep_kinds = {kinds[p] for p in keep if kinds[p]}
        keep_tokens: set[str] = set().union(*(tokens[p] for p in keep)) if keep else set()
        for pos in excess:
            replacement = next(
                (
                    a
                    for a in candidates
                    if kind_totals[a.kinds] < _kind_cap(a.category)
                    # must not re-join the group it is meant to diversify
                    and a.kinds not in keep_kinds
                    and not (_title_tokens(a.name, city_tokens) & keep_tokens)
                ),
                None,
            )
            if replacement is None:
                break
            candidates.remove(replacement)
            slot = result[act_idx[pos]]
            result[act_idx[pos]] = _draft_from_attraction(slot, replacement)
            old_kind = kinds[pos]
            if old_kind:
                kind_totals[old_kind] -= 1
            kind_totals[replacement.kinds] += 1
            swapped += 1
            logger.info(
                "variety_enforced",
                replaced=slot.title,
                with_venue=replacement.name,
                day=slot.day_number,
            )
    if swapped:
        logger.info("variety_swaps_applied", count=swapped, trip_id=str(trip.id))
    return result


def _normalize_outdoor(items: list[_ItemDraft], attractions: list[Attraction]) -> list[_ItemDraft]:
    """Ground every activity's is_outdoor flag in its matched attraction's OSM tags.

    The LLM's own flag is unreliable (open-air lidos come back "indoor"), and weather
    replanning keys on it — only swapped-in items were being corrected before.
    """
    by_ref = {a.source_ref: a for a in attractions}
    for item in items:
        if item.item_type != "activity":
            continue
        a = by_ref.get(item.source_ref or "")
        if a is not None:
            item.is_outdoor = _attraction_is_outdoor(a)
    return items


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
