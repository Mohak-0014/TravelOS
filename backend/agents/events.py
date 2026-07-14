"""Local Events agent — matches real events to open itinerary slots and proposes additions."""

from __future__ import annotations

import asyncio
import math
from datetime import date, time, timedelta

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select, update

from backend.agents._llm import build_llm
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import Approval, ItineraryItem, Trip
from backend.graphs.state import TravelOSState
from backend.tools import get_redis_client
from backend.tools.events import EventOffer, fetch_events

logger = get_logger(__name__)

_SKIP_CATEGORIES = frozenset({"Business & Professional", "Business", "Education", "Conference"})
_MAX_PROPOSALS = 3
_CONFLICT_RADIUS_M = 500.0
_EVENING_HOUR = 18


# ── Helpers ───────────────────────────────────────────────────────────────────


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in metres between two lat/lng points."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = math.sqrt(sum(x**2 for x in a))
    mag_b = math.sqrt(sum(x**2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _score_events(
    events: list[EventOffer], user_interest_text: str
) -> list[tuple[EventOffer, float]]:
    """
    Score each event by cosine similarity to the user's interest embedding.
    Falls back to score=0.5 for all if embedding is unavailable.
    """
    try:
        from backend.memory.embeddings import embed_text  # noqa: PLC0415

        user_vec = embed_text(user_interest_text)
        scored: list[tuple[EventOffer, float]] = []
        for event in events:
            event_vec = embed_text(f"{event.name} {event.category}")
            scored.append((event, _cosine_similarity(user_vec, event_vec)))
        return sorted(scored, key=lambda x: x[1], reverse=True)
    except Exception as exc:
        logger.warning("events_embedding_failed", error=str(exc))
        return [(e, 0.5) for e in events]


def _find_open_evening_slots(
    itinerary: list[dict],  # type: ignore[type-arg]
    trip_start: date,
    trip_end: date,
) -> list[tuple[int, date]]:
    """
    Return (day_number, item_date) for each trip day that has no item at 18:00 or later.
    """
    has_evening: set[date] = set()
    date_to_day: dict[date, int] = {}

    for item in itinerary:
        raw_date = item.get("item_date")
        day_number = item.get("day_number", 1)

        if isinstance(raw_date, str):
            try:
                item_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
        elif isinstance(raw_date, date):
            item_date = raw_date
        else:
            continue

        date_to_day[item_date] = day_number

        raw_time = item.get("start_time")
        if raw_time:
            if isinstance(raw_time, str):
                try:
                    start_time: time | None = time.fromisoformat(raw_time[:5])
                except ValueError:
                    start_time = None
            elif isinstance(raw_time, time):
                start_time = raw_time
            else:
                start_time = None
            if start_time and start_time.hour >= _EVENING_HOUR:
                has_evening.add(item_date)

    open_slots: list[tuple[int, date]] = []
    current = trip_start
    day_num = 1
    while current <= trip_end:
        if current not in has_evening:
            open_slots.append((date_to_day.get(current, day_num), current))
        current += timedelta(days=1)
        day_num += 1

    return open_slots


async def _proposal_summary(
    event: EventOffer,
    city: str,
    style_tags: list[str],
    day_number: int,
) -> str:
    """One sentence from a small LLM explaining why this event suits the traveller."""
    tags_str = ", ".join(style_tags[:5]) if style_tags else "travel and culture"
    try:
        llm = build_llm(size="small", temperature=0.3)
        resp = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You are a travel assistant. Output ONLY a single sentence (max 25 words) "
                        "explaining why this event suits the traveller. No markdown, no quotes."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Event: {event.name}\n"
                        f"Category: {event.category}\n"
                        f"Date: {event.event_date} (Day {day_number} of trip)\n"
                        f"City: {city}\n"
                        f"Venue: {event.venue_name}\n"
                        f"Traveller interests: {tags_str}"
                    )
                ),
            ]
        )
        return str(resp.content).strip()
    except Exception as exc:
        logger.warning("events_llm_summary_failed", error=str(exc))
        return f"{event.name} on Day {day_number} — matches your interests in {tags_str}."


# ── Entry point ───────────────────────────────────────────────────────────────


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state["trip_id"]

    # Step 1: Load trip
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Trip).where(Trip.id == trip_id))
            trip = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("events_agent_db_load_failed", trip_id=trip_id, error=str(exc))
        trip = None

    if trip is None:
        logger.warning("events_agent_no_trip", trip_id=trip_id)
        return {
            "events_state": {"fetched": 0, "filtered": 0, "proposed": [], "conflict_warnings": 0},
            "agent_messages": [AIMessage(content="Events agent: trip not found, skipping.")],
        }

    city = trip.destination_city
    country = trip.destination_country
    start_date = trip.start_date
    end_date = trip.end_date

    # Step 2: Fetch from both APIs in parallel
    try:
        cache = get_redis_client()
    except Exception:
        cache = None

    events = await fetch_events(
        city=city,
        country=country,
        start_date=start_date,
        end_date=end_date,
        ticketmaster_key=settings.TICKETMASTER_API_KEY,
        eventbrite_token=settings.EVENTBRITE_TOKEN,
        cache=cache,
    )
    fetched = len(events)

    # Step 3: Filter — require coordinates, correct date range, travel-relevant category
    filtered = [
        e
        for e in events
        if e.lat is not None
        and e.lng is not None
        and start_date <= e.event_date <= end_date
        and e.category not in _SKIP_CATEGORIES
    ]

    logger.info("events_filtered", trip_id=trip_id, fetched=fetched, kept=len(filtered))

    if not filtered:
        return {
            "events_state": {
                "fetched": fetched,
                "filtered": 0,
                "proposed": [],
                "conflict_warnings": 0,
            },
            "agent_messages": [
                AIMessage(content=f"Events agent: {fetched} fetched, none passed filters.")
            ],
        }

    # Step 4: Score by interest similarity (embedding cosine similarity, sync in executor)
    memory = state.get("memory_context") or {}
    profile = memory.get("travel_style_profile") or {}
    prefs = memory.get("preferences") or {}
    style_tags: list[str] = profile.get("style_tags") or []
    interests: list[str] = prefs.get("interests") or []
    user_interest_text = " ".join(style_tags + interests) or "travel sightseeing culture food"

    loop = asyncio.get_event_loop()
    scored = await loop.run_in_executor(None, _score_events, filtered, user_interest_text)
    top10 = scored[:10]

    # Step 5: Match top-scored events to open evening slots (first-fit by date)
    itinerary: list[dict] = state.get("itinerary") or []  # type: ignore[type-arg]
    open_slots = _find_open_evening_slots(itinerary, start_date, end_date)

    proposals: list[tuple[EventOffer, int]] = []  # slot-matched → pending approval
    auto_events: list[tuple[EventOffer, int]] = []  # unmatched → auto-approved for browsing
    used_dates: set[date] = set()
    proposed_event_names: set[str] = set()

    for event, _score in top10:
        matched = False
        if len(proposals) < _MAX_PROPOSALS:
            for day_num, slot_date in open_slots:
                if slot_date == event.event_date and slot_date not in used_dates:
                    proposals.append((event, day_num))
                    used_dates.add(slot_date)
                    proposed_event_names.add(event.name)
                    matched = True
                    break
        if not matched:
            # Store for display even without a matching open slot
            day_offset = (event.event_date - start_date).days + 1
            day_num = max(1, min(day_offset, (end_date - start_date).days + 1))
            auto_events.append((event, day_num))

    # Step 6: Venue conflict detection — flag existing items within 500m of a top-10 event
    conflict_count = 0
    async with AsyncSessionLocal() as db:
        for event, _score in top10:
            if event.lat is None or event.lng is None:
                continue
            items_result = await db.execute(
                select(ItineraryItem).where(
                    ItineraryItem.trip_id == trip_id,
                    ItineraryItem.item_date == event.event_date,
                )
            )
            for item in items_result.scalars().all():
                if item.latitude is None or item.longitude is None:
                    continue
                dist = _haversine_m(
                    float(item.latitude), float(item.longitude), event.lat, event.lng
                )
                if dist < _CONFLICT_RADIUS_M:
                    warning = (
                        f"Large event nearby: {event.name} at {event.venue_name} "
                        f"({int(dist)}m away) — expect crowds on this day."
                    )
                    await db.execute(
                        update(ItineraryItem)
                        .where(ItineraryItem.id == item.id)
                        .values(conflict_warning=warning)
                    )
                    conflict_count += 1
        if conflict_count:
            await db.commit()

    # Steps 7 + 8: LLM summaries → ApprovalRequests
    proposed_names: list[str] = []

    def _event_payload(event: EventOffer, day_num: int) -> dict:  # type: ignore[type-arg]
        return {
            "event_name": event.name,
            "event_date": event.event_date.isoformat(),
            "start_time": event.start_time.isoformat() if event.start_time else None,
            "venue_name": event.venue_name,
            "lat": event.lat,
            "lng": event.lng,
            "category": event.category,
            "price_min": event.price_min,
            "price_max": event.price_max,
            "price_currency": event.price_currency,
            "url": event.url,
            "image_url": event.image_url,
            "day_number": day_num,
            "source": event.source,
        }

    async with AsyncSessionLocal() as db:
        # Pending proposals — require user action
        for event, day_num in proposals:
            summary = await _proposal_summary(event, city, style_tags, day_num)
            db.add(
                Approval(
                    trip_id=trip_id,
                    proposed_by="events_agent",
                    change_type="event_add",
                    summary=summary,
                    payload=_event_payload(event, day_num),
                    status="pending",
                )
            )
            proposed_names.append(event.name)

        # Auto-approved events — stored for browsing, no user action needed
        for event, day_num in auto_events:
            summary = f"{event.name} at {event.venue_name}"
            db.add(
                Approval(
                    trip_id=trip_id,
                    proposed_by="events_agent",
                    change_type="event_add",
                    summary=summary,
                    payload=_event_payload(event, day_num),
                    status="approved",
                )
            )

        if proposals:
            trip_result = await db.execute(select(Trip).where(Trip.id == trip_id))
            db_trip = trip_result.scalar_one_or_none()
            if db_trip:
                db_trip.status = "awaiting_approval"
        await db.commit()

    logger.info(
        "events_agent_done",
        trip_id=trip_id,
        proposed=len(proposed_names),
        auto=len(auto_events),
        conflict_warnings=conflict_count,
    )

    msg = (
        f"Events agent: {fetched} fetched, {len(filtered)} filtered, "
        f"{len(proposed_names)} pending proposals, {len(auto_events)} auto-displayed, "
        f"{conflict_count} conflict warnings."
    )
    return {
        "events_state": {
            "fetched": fetched,
            "filtered": len(filtered),
            "proposed": proposed_names,
            "auto_displayed": len(auto_events),
            "conflict_warnings": conflict_count,
        },
        "agent_messages": [AIMessage(content=msg)],
    }
