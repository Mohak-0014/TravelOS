import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta
from datetime import time as dtime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_cache, get_current_active_user, get_owned_trip
from backend.api.rate_limit import limiter
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import get_db
from backend.db.models import Approval, HotelCandidate, ItineraryItem, TravelerProfile, Trip, User
from backend.db.schemas import (
    HotelCandidateOut,
    ItineraryItemCreate,
    ItineraryItemOut,
    ItineraryItemUpdate,
    TripCreate,
    TripOut,
    TripUpdate,
)
from backend.tools import redis_get_cached, redis_set_cached
from backend.tools.flights import FlightOffer, search_flights
from backend.tools.geocode import geocode
from backend.tools.weather import WeatherDay, fetch_weather

logger = get_logger(__name__)


_UNSPLASH_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days — a stable cover photo per city is fine


async def _fetch_unsplash_photo(city: str, cache: Redis | None = None) -> str | None:  # type: ignore[type-arg]
    """Fetch a landscape travel photo URL from Unsplash. Best-effort — None on failure.

    Cached per city: the endpoint is "random", but a stable cover image per city is fine
    and keeps us from re-rolling (and burning Unsplash quota) on every create/edit.
    """
    if not settings.UNSPLASH_ACCESS_KEY:
        return None

    key = f"unsplash:{city.lower().strip()}"
    cached = await redis_get_cached(cache, key)
    if isinstance(cached, str):
        return cached

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                "https://api.unsplash.com/photos/random",
                params={"query": f"{city} travel landmark", "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY}"},
            )
            if r.status_code == 200:
                data = r.json()
                url: str | None = data.get("urls", {}).get("regular") or None
                if url:
                    await redis_set_cached(cache, key, url, _UNSPLASH_CACHE_TTL)
                return url
    except Exception as exc:
        logger.warning("unsplash_fetch_failed", city=city, error=str(exc))
    return None


def _ics_escape(value: str) -> str:
    """Escape a text value per RFC 5545 so it can't inject ICS properties or newlines."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _build_ics(trip: Trip, items: list[ItineraryItem]) -> str:
    """Generate an ICS (iCalendar) file string for a trip's itinerary."""
    now_str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = trip.destination_city
    if trip.destination_country:
        dest += f", {trip.destination_country}"
    dest = _ics_escape(dest)

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TravelOS//AI Travel Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{dest} Trip",
    ]

    for item in items:
        if item.item_date is None:
            continue

        start_t: dtime = item.start_time if item.start_time else dtime(9, 0)
        if item.end_time:
            end_t: dtime = item.end_time
        else:
            end_h = (start_t.hour + 1) % 24
            end_t = dtime(end_h, start_t.minute)

        date_str = item.item_date.strftime("%Y%m%d")
        dtstart = f"{date_str}T{start_t.strftime('%H%M%S')}"
        dtend = f"{date_str}T{end_t.strftime('%H%M%S')}"

        # Escape special characters per RFC 5545
        summary = _ics_escape(item.title or "")
        desc = _ics_escape(item.description or "")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{item.id}@travelos.app",
            f"DTSTAMP:{now_str}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            f"LOCATION:{dest}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


router = APIRouter(prefix="/api/v1/trips", tags=["trips"])


# ── Trip CRUD ─────────────────────────────────────────────────────────────────


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # geocode (Nominatim 1 req/s policy) + Unsplash on each call
async def create_trip(
    request: Request,
    body: TripCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cache: Redis = Depends(get_cache),  # type: ignore[type-arg]
) -> Trip:
    if body.end_date < body.start_date:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "end_date must be >= start_date."},
        )

    # Geocode + Unsplash are independent and best-effort — run them concurrently and
    # still create the trip if either fails.
    geo, cover_url = await asyncio.gather(
        geocode(f"{body.destination_city}, {body.destination_country or ''}", cache=cache),
        _fetch_unsplash_photo(body.destination_city, cache=cache),
    )

    trip = Trip(
        user_id=current_user.id,
        title=body.title,
        destination_city=body.destination_city,
        # Backfill from geocoding when the user left country blank — hotel search
        # (LiteAPI countryCode), local-currency detection, and airport resolution
        # all degrade without one.
        destination_country=body.destination_country or (geo.country if geo else None),
        latitude=geo.lat if geo else None,
        longitude=geo.lng if geo else None,
        start_date=body.start_date,
        end_date=body.end_date,
        num_travelers=body.num_travelers,
        budget_total=body.budget_total,
        budget_currency=body.budget_currency,
        flight_origin=body.flight_origin,
        cover_image_url=cover_url,
    )
    db.add(trip)
    await db.flush()

    lead = TravelerProfile(
        trip_id=trip.id,
        display_name=current_user.full_name or current_user.email,
        is_lead=True,
    )
    db.add(lead)

    await db.commit()
    await db.refresh(trip)
    return trip


@router.get("", response_model=list[TripOut])
async def list_trips(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[Trip]:
    result = await db.execute(
        select(Trip)
        .where(Trip.user_id == current_user.id, Trip.status != "cancelled")
        .offset(skip)
        .limit(limit)
        .order_by(Trip.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{trip_id}", response_model=TripOut)
async def get_trip(trip: Trip = Depends(get_owned_trip)) -> Trip:
    return trip


@router.put("/{trip_id}", response_model=TripOut)
@limiter.limit("20/minute")  # may re-geocode + refetch Unsplash when destination changes
async def update_trip(
    request: Request,
    body: TripUpdate,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
    cache: Redis = Depends(get_cache),  # type: ignore[type-arg]
) -> Trip:
    updates = body.model_dump(exclude_none=True)
    start = updates.get("start_date", trip.start_date)
    end = updates.get("end_date", trip.end_date)
    if end < start:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "end_date must be >= start_date."},
        )

    for field, value in updates.items():
        setattr(trip, field, value)

    # Re-geocode + refresh cover photo if destination changed (concurrent, best-effort)
    if "destination_city" in updates or "destination_country" in updates:
        city = updates.get("destination_city", trip.destination_city)
        country = updates.get("destination_country", trip.destination_country) or ""
        geo, cover_url = await asyncio.gather(
            geocode(f"{city}, {country}", cache=cache),
            _fetch_unsplash_photo(city, cache=cache),
        )
        if geo:
            trip.latitude = geo.lat
            trip.longitude = geo.lng
            if not trip.destination_country and geo.country:
                trip.destination_country = geo.country
        if cover_url:
            trip.cover_image_url = cover_url

    await db.commit()
    await db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_trip(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> None:
    trip.status = "cancelled"
    await db.commit()


# ── Itinerary ─────────────────────────────────────────────────────────────────


@router.get("/{trip_id}/itinerary", response_model=list[ItineraryItemOut])
async def get_itinerary(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> list[ItineraryItem]:
    items = await db.execute(
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip.id)
        .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
    )
    return list(items.scalars().all())


@router.post(
    "/{trip_id}/itinerary",
    response_model=ItineraryItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_itinerary_item(
    body: ItineraryItemCreate,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> ItineraryItem:
    item_date = body.item_date
    if item_date < trip.start_date or item_date > trip.end_date:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "item_date outside trip date range."},
        )

    item = ItineraryItem(
        trip_id=trip.id,
        **body.model_dump(),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{trip_id}/itinerary/{item_id}", response_model=ItineraryItemOut)
async def update_itinerary_item(
    item_id: str,
    body: ItineraryItemUpdate,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> ItineraryItem:
    item_result = await db.execute(
        select(ItineraryItem).where(ItineraryItem.id == item_id, ItineraryItem.trip_id == trip.id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found."}
        )

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{trip_id}/itinerary/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_itinerary_item(
    item_id: str,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> None:
    item_result = await db.execute(
        select(ItineraryItem).where(ItineraryItem.id == item_id, ItineraryItem.trip_id == trip.id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found."}
        )

    await db.delete(item)
    await db.commit()


@router.post("/{trip_id}/itinerary/generate")
@limiter.limit("10/minute")  # enqueues the full multi-agent graph — the heaviest op
async def generate_itinerary(
    request: Request,
    trip: Trip = Depends(get_owned_trip),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    # Only block when a run is already in flight — otherwise allow regeneration from
    # any settled state (planned / awaiting_approval / failed) so the "Regenerate"
    # button works on completed trips, not just freshly-created ones.
    if trip.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONFLICT",
                "message": "Itinerary generation is already in progress for this trip.",
            },
        )

    from backend.workflows.celery_tasks import generate_itinerary_async  # noqa: PLC0415

    generate_itinerary_async.delay(str(trip.id), str(current_user.id))
    return {"status": "queued", "trip_id": str(trip.id)}


# ── Hotels ───────────────────────────────────────────────────────────────────


@router.get("/{trip_id}/hotels", response_model=list[HotelCandidateOut])
async def get_trip_hotels(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> list[HotelCandidate]:
    hotels = await db.execute(
        select(HotelCandidate)
        .where(HotelCandidate.trip_id == trip.id)
        .order_by(HotelCandidate.match_score.desc().nulls_last())
    )
    return list(hotels.scalars().all())


# ── Hotel selection ───────────────────────────────────────────────────────────


@router.post("/{trip_id}/hotels/{hotel_id}/select", response_model=list[HotelCandidateOut])
async def select_hotel(
    hotel_id: str,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> list[HotelCandidate]:
    hotels_result = await db.execute(
        select(HotelCandidate)
        .where(HotelCandidate.trip_id == trip.id)
        .order_by(HotelCandidate.match_score.desc().nulls_last())
    )
    candidates = list(hotels_result.scalars().all())

    if not any(c.id == hotel_id for c in candidates):
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Hotel not found."}
        )

    for c in candidates:
        c.is_selected = c.id == hotel_id

    await db.commit()
    for c in candidates:
        await db.refresh(c)
    return candidates


# ── Calendar export ────────────────────────────────────────────────────────────


@router.get("/{trip_id}/calendar.ics")
async def get_calendar_ics(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> Response:
    items_result = await db.execute(
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip.id)
        .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
    )
    items = list(items_result.scalars().all())

    ics_content = _build_ics(trip, items)
    safe_city = re.sub(r"[^a-z0-9]+", "-", trip.destination_city.lower()).strip("-") or "trip"
    filename = f"travelos-{safe_city}.ics"
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Weather ───────────────────────────────────────────────────────────────────


@router.get("/{trip_id}/weather", response_model=list[WeatherDay])
@limiter.limit("30/minute")  # hits Open-Meteo (+ Nominatim fallback) — external APIs
async def get_trip_weather(
    request: Request,
    trip: Trip = Depends(get_owned_trip),
    cache: Redis = Depends(get_cache),  # type: ignore[type-arg]
) -> list[WeatherDay]:
    lat, lng = trip.latitude, trip.longitude
    if lat is None or lng is None:
        geo = await geocode(
            f"{trip.destination_city}, {trip.destination_country or ''}", cache=cache
        )
        if geo is None:
            return []
        lat, lng = geo.lat, geo.lng

    return await fetch_weather(lat, lng, trip.start_date, trip.end_date)


# ── Flights ──────────────────────────────────────────────────────────────────


@router.get("/{trip_id}/flights", response_model=list[FlightOffer])
@limiter.limit("20/minute")  # Duffel — external commercial flight-search API
async def get_trip_flights(
    request: Request,
    origin: str = Query(..., description="Departure airport IATA code (e.g. DEL, JFK, LHR)"),
    trip: Trip = Depends(get_owned_trip),
    cache: Redis = Depends(get_cache),  # type: ignore[type-arg]
) -> list[FlightOffer]:
    """Search round-trip flights from the given origin airport using Duffel."""
    if len(origin) != 3 or not origin.isalpha():
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "origin must be a 3-letter IATA code."},
        )

    return await search_flights(
        origin_iata=origin.upper(),
        destination_city=trip.destination_city,
        departure_date=trip.start_date,
        return_date=trip.end_date,
        num_travelers=trip.num_travelers,
        currency=trip.budget_currency or "USD",
        api_key=settings.DUFFEL_API_KEY,
        cache=cache,
        near=(
            (float(trip.latitude), float(trip.longitude))
            if trip.latitude is not None and trip.longitude is not None
            else None
        ),
    )


# ── Events ───────────────────────────────────────────────────────────────────


@router.get("/{trip_id}/events")
async def list_trip_events(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:  # type: ignore[type-arg]
    """Return all event_add approvals for the trip as browsable event cards."""
    rows = await db.execute(
        select(Approval)
        .where(Approval.trip_id == trip.id, Approval.change_type == "event_add")
        .order_by(Approval.created_at)
    )
    events = []
    for approval in rows.scalars().all():
        p = approval.payload or {}
        events.append(
            {
                "id": str(approval.id),
                "approval_status": approval.status,
                "event_name": p.get("event_name", ""),
                "event_date": p.get("event_date"),
                "start_time": p.get("start_time"),
                "venue_name": p.get("venue_name", ""),
                "category": p.get("category", ""),
                "source": p.get("source", ""),
                "url": p.get("url"),
                "image_url": p.get("image_url"),
                "price_min": p.get("price_min"),
                "price_max": p.get("price_max"),
                "price_currency": p.get("price_currency"),
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "day_number": p.get("day_number"),
                "summary": approval.summary or "",
            }
        )
    return events


# ── Share ─────────────────────────────────────────────────────────────────────


@router.post("/{trip_id}/share", response_model=TripOut)
async def create_share_link(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    trip.share_token = str(uuid.uuid4())
    trip.share_expires_at = datetime.now(UTC) + timedelta(days=30)
    await db.commit()
    await db.refresh(trip)
    return trip
