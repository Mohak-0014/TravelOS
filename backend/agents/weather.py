"""Weather Adaptation agent — detects adverse weather and proposes itinerary replanning.

Replacement activities are drawn from the real OSM attraction pool (grounding guardrail:
never fabricate a venue). If no indoor venue is available, no proposal is made.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from langchain_core.messages import SystemMessage
from sqlalchemy import select

from backend.agents.itinerary_planner import _attraction_is_outdoor
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import Approval, ItineraryItem, Trip, WeatherSnapshot
from backend.graphs.state import TravelOSState
from backend.tools.geocode import geocode
from backend.tools.places import Attraction, search_attractions
from backend.tools.weather import WeatherDay, fetch_weather

logger = get_logger(__name__)

_POOL_RADIUS_M = 12000
_POOL_LIMIT = 30


# ── Node 1: weather_check ─────────────────────────────────────────────────────


async def weather_check(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    logger.info("weather_check_start", trip_id=trip_id)

    trip = await _load_trip(trip_id)
    if trip is None:
        logger.error("weather_check_trip_not_found", trip_id=trip_id)
        return {
            "weather_state": _empty_weather_state(),
            "current_step": "impact_assessment",
            "agent_messages": [SystemMessage(content=f"Weather Agent: trip {trip_id} not found.")],
        }

    coords = await _resolve_coords(trip)
    if not coords:
        logger.warning("weather_check_no_coords", trip_id=trip_id)
        return {
            "weather_state": _empty_weather_state(),
            "current_step": "impact_assessment",
            "agent_messages": [
                SystemMessage(
                    content=f"Weather Agent: could not resolve coords for {trip.destination_city}."
                )
            ],
        }

    lat, lng = coords
    weather_days = await fetch_weather(lat, lng, trip.start_date, trip.end_date)
    await _save_weather_snapshots(trip_id, weather_days)

    risk_flags = [w.date.isoformat() for w in weather_days if w.is_adverse]
    forecast = [
        {
            "date": w.date.isoformat(),
            "condition": w.condition_label,
            "temp_min_c": w.temp_min_c,
            "temp_max_c": w.temp_max_c,
            "precipitation_mm": w.precipitation_mm,
            "is_adverse": w.is_adverse,
        }
        for w in weather_days
    ]

    logger.info("weather_check_complete", trip_id=trip_id, adverse_days=len(risk_flags))

    return {
        "weather_state": {
            "risk_flags": risk_flags,
            "last_checked": datetime.now(UTC).isoformat(),
            "forecast": forecast,
            "affected_items": [],
        },
        "current_step": "impact_assessment",
        "agent_messages": [
            SystemMessage(
                content=(
                    f"Weather Agent: fetched {len(weather_days)}-day forecast"
                    f" for {trip.destination_city}. Adverse days: {risk_flags or 'none'}"
                )
            )
        ],
    }


# ── Node 2: impact_assessment ─────────────────────────────────────────────────


async def impact_assessment(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    weather_state = dict(state.get("weather_state") or {})
    risk_flags: list[str] = weather_state.get("risk_flags") or []

    logger.info("impact_assessment_start", trip_id=trip_id, adverse_days=len(risk_flags))

    if not risk_flags:
        weather_state["affected_items"] = []
        return {
            "weather_state": weather_state,
            "current_step": "weather_adaptation",
        }

    affected = await _load_affected_items(trip_id, risk_flags)
    weather_state["affected_items"] = affected

    logger.info("impact_assessment_complete", trip_id=trip_id, affected=len(affected))

    return {
        "weather_state": weather_state,
        "current_step": "weather_adaptation",
        "agent_messages": [
            SystemMessage(
                content=(
                    f"Weather Agent: {len(affected)} outdoor item(s) conflict"
                    " with adverse weather days."
                )
            )
        ],
    }


# ── Node 3: weather_adaptation ────────────────────────────────────────────────


async def weather_adaptation(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    weather_state = state.get("weather_state") or {}
    affected_items: list[dict] = weather_state.get("affected_items") or []  # type: ignore[type-arg]

    logger.info("weather_adaptation_start", trip_id=trip_id, items=len(affected_items))

    if not affected_items:
        return {
            "approval_queue": list(state.get("approval_queue") or []),
            "current_step": "create_approvals",
        }

    trip = await _load_trip(trip_id)

    # Real indoor venues near the destination, best-scored first. Grounding: a
    # replacement the user approves must exist — never let the LLM invent one.
    candidates = await _indoor_candidates(trip, trip_id)

    new_approvals: list[dict] = []  # type: ignore[type-arg]
    for item in affected_items:
        alternative = _next_alternative(candidates)
        if alternative:
            new_approvals.append(_build_approval(trip_id, item, alternative, weather_state))
        else:
            logger.warning("weather_no_indoor_alternative", trip_id=trip_id, item=item.get("title"))

    existing_queue: list[dict] = list(state.get("approval_queue") or [])  # type: ignore[type-arg]

    logger.info("weather_adaptation_complete", trip_id=trip_id, proposals=len(new_approvals))

    return {
        "approval_queue": existing_queue + new_approvals,
        "current_step": "create_approvals",
        "agent_messages": [
            SystemMessage(
                content=f"Weather Agent: {len(new_approvals)} indoor alternative(s) proposed."
            )
        ],
    }


# ── Node 4: create_approvals ──────────────────────────────────────────────────


async def create_approvals(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    approval_queue: list[dict] = list(state.get("approval_queue") or [])  # type: ignore[type-arg]
    weather_approvals = [a for a in approval_queue if a.get("change_type") == "weather_replan"]

    logger.info("create_approvals_start", trip_id=trip_id, approvals=len(weather_approvals))

    if weather_approvals:
        await _persist_approvals(trip_id, weather_approvals)
        await _set_trip_awaiting_approval(trip_id)

    logger.info("create_approvals_complete", trip_id=trip_id)
    return {"current_step": "end"}


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _load_trip(trip_id: str) -> Trip | None:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Trip).where(Trip.id == trip_id))
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("weather_agent_db_load_error", trip_id=trip_id, error=str(exc))
        return None


async def _resolve_coords(trip: Trip) -> tuple[float, float] | None:
    if trip.latitude is not None and trip.longitude is not None:
        return trip.latitude, trip.longitude
    query = f"{trip.destination_city}, {trip.destination_country or ''}"
    point = await geocode(query)
    return (point.lat, point.lng) if point else None


async def _save_weather_snapshots(trip_id: str, weather_days: list[WeatherDay]) -> None:
    if not weather_days:
        return
    try:
        async with AsyncSessionLocal() as session:
            for w in weather_days:
                existing = await session.execute(
                    select(WeatherSnapshot).where(
                        WeatherSnapshot.trip_id == trip_id,
                        WeatherSnapshot.snapshot_date == w.date,
                    )
                )
                row = existing.scalar_one_or_none()
                if row is None:
                    session.add(
                        WeatherSnapshot(
                            trip_id=trip_id,
                            snapshot_date=w.date,
                            temp_min_c=w.temp_min_c,
                            temp_max_c=w.temp_max_c,
                            precipitation_mm=w.precipitation_mm,
                            condition_code=w.condition_code,
                            is_adverse=w.is_adverse,
                        )
                    )
                else:
                    row.temp_min_c = w.temp_min_c
                    row.temp_max_c = w.temp_max_c
                    row.precipitation_mm = w.precipitation_mm
                    row.condition_code = w.condition_code
                    row.is_adverse = w.is_adverse
            await session.commit()
            logger.info("weather_snapshots_saved", trip_id=trip_id, count=len(weather_days))
    except Exception as exc:
        logger.error("weather_snapshots_save_error", trip_id=trip_id, error=str(exc))


async def _load_affected_items(trip_id: str, risk_flags: list[str]) -> list[dict]:  # type: ignore[type-arg]
    try:
        adverse_dates = [date.fromisoformat(d) for d in risk_flags]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ItineraryItem).where(
                    ItineraryItem.trip_id == trip_id,
                    ItineraryItem.is_outdoor.is_(True),
                    ItineraryItem.item_date.in_(adverse_dates),
                )
            )
            rows = result.scalars().all()
            return [_item_to_dict(r) for r in rows]
    except Exception as exc:
        logger.error("weather_load_affected_error", trip_id=trip_id, error=str(exc))
        return []


async def _persist_approvals(trip_id: str, approvals: list[dict]) -> None:  # type: ignore[type-arg]
    try:
        async with AsyncSessionLocal() as session:
            for item in approvals:
                item_id = str(item.get("id") or "")
                if not item_id:
                    continue
                existing = await session.get(Approval, item_id)
                if existing is None:
                    session.add(
                        Approval(
                            id=item_id,
                            trip_id=trip_id,
                            proposed_by=item.get("proposed_by") or "weather_agent",
                            change_type=item.get("change_type") or "weather_replan",
                            summary=item.get("summary") or "",
                            payload=item.get("payload") or {},
                            status="pending",
                        )
                    )
            await session.commit()
            logger.info("weather_approvals_persisted", trip_id=trip_id, count=len(approvals))
    except Exception as exc:
        logger.error("weather_persist_approvals_error", trip_id=trip_id, error=str(exc))


async def _set_trip_awaiting_approval(trip_id: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            trip = await session.get(Trip, trip_id)
            if trip is not None:
                trip.status = "awaiting_approval"
                await session.commit()
    except Exception as exc:
        logger.error("weather_set_status_error", trip_id=trip_id, error=str(exc))


# ── Alternative selection (grounded) ──────────────────────────────────────────


async def _indoor_candidates(trip: Trip | None, trip_id: str) -> list[Attraction]:
    """Real indoor venues near the destination, best-scored first, minus venues
    already scheduled on this trip. Degrades to [] — then no proposal is made."""
    if trip is None:
        return []
    coords = await _resolve_coords(trip)
    if not coords:
        return []
    lat, lng = coords
    try:
        pool = await search_attractions(lat, lng, radius_m=_POOL_RADIUS_M, limit=_POOL_LIMIT)
    except Exception as exc:
        logger.warning("weather_pool_fetch_failed", trip_id=trip_id, error=str(exc))
        return []
    scheduled = await _scheduled_refs_and_names(trip_id)
    return [
        a
        for a in pool
        if not _attraction_is_outdoor(a)
        and a.source_ref not in scheduled
        and a.name.lower() not in scheduled
    ]


async def _scheduled_refs_and_names(trip_id: str) -> set[str]:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ItineraryItem.source_ref, ItineraryItem.title).where(
                    ItineraryItem.trip_id == trip_id
                )
            )
            out: set[str] = set()
            for ref, title in result.all():
                if ref:
                    out.add(ref)
                if title:
                    out.add(title.lower())
            return out
    except Exception as exc:
        logger.error("weather_scheduled_refs_error", trip_id=trip_id, error=str(exc))
        return set()


def _next_alternative(candidates: list[Attraction]) -> dict | None:  # type: ignore[type-arg]
    """Pop the best unused indoor venue as a grounded replacement draft."""
    if not candidates:
        return None
    attraction = candidates.pop(0)
    return {
        "title": attraction.name,
        "description": attraction.kinds,
        "item_type": "activity",
        "is_outdoor": False,
        "latitude": attraction.lat,
        "longitude": attraction.lng,
        "source_provider": "overpass",
        "source_ref": attraction.source_ref,
    }


def _build_approval(
    trip_id: str,
    item: dict,  # type: ignore[type-arg]
    alternative: dict,  # type: ignore[type-arg]
    weather_state: dict,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    return {
        "id": str(uuid.uuid4()),
        "trip_id": trip_id,
        "proposed_by": "weather_agent",
        "change_type": "weather_replan",
        "summary": (
            f"Replace '{item.get('title')}' on {item.get('item_date')} "
            f"with '{alternative.get('title')}' due to adverse weather"
        ),
        "payload": {
            "original_item": item,
            "alternative_item": {
                **alternative,
                "day_number": item.get("day_number"),
                "item_date": item.get("item_date"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
                "sort_order": item.get("sort_order", 0),
            },
            "weather_condition": _condition_for_date(
                str(item.get("item_date", "")), weather_state.get("forecast") or []
            ),
        },
        "status": "pending",
    }


def _condition_for_date(item_date: str, forecast: list[dict]) -> str:  # type: ignore[type-arg]
    for f in forecast:
        if f.get("date") == item_date:
            return str(f.get("condition", "Adverse weather"))
    return "Adverse weather"


# ── Misc helpers ──────────────────────────────────────────────────────────────


def _empty_weather_state() -> dict:  # type: ignore[type-arg]
    return {
        "risk_flags": [],
        "last_checked": datetime.now(UTC).isoformat(),
        "forecast": [],
        "affected_items": [],
    }


def _item_to_dict(item: ItineraryItem) -> dict:  # type: ignore[type-arg]
    return {
        "id": str(item.id),
        "trip_id": str(item.trip_id),
        "day_number": item.day_number,
        "item_date": item.item_date.isoformat(),
        "start_time": item.start_time.strftime("%H:%M") if item.start_time else None,
        "end_time": item.end_time.strftime("%H:%M") if item.end_time else None,
        "item_type": item.item_type,
        "title": item.title,
        "description": item.description,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "address": item.address,
        "source_provider": item.source_provider,
        "source_ref": item.source_ref,
        "est_cost": float(item.est_cost) if item.est_cost is not None else None,
        "est_cost_currency": item.est_cost_currency,
        "is_outdoor": item.is_outdoor,
        "sort_order": item.sort_order,
    }
