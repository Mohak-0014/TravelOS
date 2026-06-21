import uuid
from datetime import UTC, datetime, timedelta
from datetime import time as dtime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_active_user
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import get_db
from backend.db.models import HotelCandidate, ItineraryItem, TravelerProfile, Trip, User
from backend.db.schemas import (
    HotelCandidateOut,
    ItineraryItemCreate,
    ItineraryItemOut,
    ItineraryItemUpdate,
    TripCreate,
    TripOut,
    TripUpdate,
)
from backend.tools.geocode import geocode
from backend.tools.weather import WeatherDay, fetch_weather

logger = get_logger(__name__)


async def _fetch_unsplash_photo(city: str) -> str | None:
    """Fetch a landscape travel photo URL from Unsplash. Best-effort — None on failure."""
    if not settings.UNSPLASH_ACCESS_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                "https://api.unsplash.com/photos/random",
                params={"query": f"{city} travel landmark", "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY}"},
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("urls", {}).get("regular") or None
    except Exception as exc:
        logger.warning("unsplash_fetch_failed", city=city, error=str(exc))
    return None


def _build_ics(trip: Trip, items: list[ItineraryItem]) -> str:
    """Generate an ICS (iCalendar) file string for a trip's itinerary."""
    now_str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = trip.destination_city
    if trip.destination_country:
        dest += f", {trip.destination_country}"

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
        summary = (item.title or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
        desc = (
            (item.description or "").replace("\\", "\\\\").replace(",", "\\,").replace("\n", "\\n")
        )

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


def _assert_owns(trip: Trip | None, user: User) -> Trip:
    if trip is None or trip.user_id != user.id:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Trip not found."}
        )
    return trip


# ── Trip CRUD ─────────────────────────────────────────────────────────────────


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
async def create_trip(
    body: TripCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    if body.end_date < body.start_date:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "end_date must be >= start_date."},
        )

    # Geocode + Unsplash — both best-effort, trip still created on failure
    geo = await geocode(f"{body.destination_city}, {body.destination_country or ''}")
    cover_url = await _fetch_unsplash_photo(body.destination_city)

    trip = Trip(
        user_id=current_user.id,
        title=body.title,
        destination_city=body.destination_city,
        destination_country=body.destination_country,
        latitude=geo.lat if geo else None,
        longitude=geo.lng if geo else None,
        start_date=body.start_date,
        end_date=body.end_date,
        num_travelers=body.num_travelers,
        budget_total=body.budget_total,
        budget_currency=body.budget_currency,
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
async def get_trip(
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    return _assert_owns(result.scalar_one_or_none(), current_user)


@router.put("/{trip_id}", response_model=TripOut)
async def update_trip(
    trip_id: str,
    body: TripUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_owns(result.scalar_one_or_none(), current_user)

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

    # Re-geocode + refresh cover photo if destination changed
    if "destination_city" in updates or "destination_country" in updates:
        city = updates.get("destination_city", trip.destination_city)
        country = updates.get("destination_country", trip.destination_country) or ""
        geo = await geocode(f"{city}, {country}")
        if geo:
            trip.latitude = geo.lat
            trip.longitude = geo.lng
        cover_url = await _fetch_unsplash_photo(city)
        if cover_url:
            trip.cover_image_url = cover_url

    await db.commit()
    await db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_trip(
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_owns(result.scalar_one_or_none(), current_user)
    trip.status = "cancelled"
    await db.commit()


# ── Itinerary ─────────────────────────────────────────────────────────────────


@router.get("/{trip_id}/itinerary", response_model=list[ItineraryItemOut])
async def get_itinerary(
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ItineraryItem]:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    _assert_owns(result.scalar_one_or_none(), current_user)

    items = await db.execute(
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
    )
    return list(items.scalars().all())


@router.post(
    "/{trip_id}/itinerary",
    response_model=ItineraryItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_itinerary_item(
    trip_id: str,
    body: ItineraryItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ItineraryItem:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_owns(result.scalar_one_or_none(), current_user)

    item_date = body.item_date
    if item_date < trip.start_date or item_date > trip.end_date:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "item_date outside trip date range."},
        )

    item = ItineraryItem(
        trip_id=trip_id,
        **body.model_dump(),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{trip_id}/itinerary/{item_id}", response_model=ItineraryItemOut)
async def update_itinerary_item(
    trip_id: str,
    item_id: str,
    body: ItineraryItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ItineraryItem:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    _assert_owns(result.scalar_one_or_none(), current_user)

    item_result = await db.execute(
        select(ItineraryItem).where(ItineraryItem.id == item_id, ItineraryItem.trip_id == trip_id)
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
    trip_id: str,
    item_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    _assert_owns(result.scalar_one_or_none(), current_user)

    item_result = await db.execute(
        select(ItineraryItem).where(ItineraryItem.id == item_id, ItineraryItem.trip_id == trip_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found."}
        )

    await db.delete(item)
    await db.commit()


@router.post("/{trip_id}/itinerary/generate")
async def generate_itinerary(
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_owns(result.scalar_one_or_none(), current_user)

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
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[HotelCandidate]:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    _assert_owns(result.scalar_one_or_none(), current_user)

    hotels = await db.execute(
        select(HotelCandidate)
        .where(HotelCandidate.trip_id == trip_id)
        .order_by(HotelCandidate.match_score.desc().nulls_last())
    )
    return list(hotels.scalars().all())


# ── Hotel selection ───────────────────────────────────────────────────────────


@router.post("/{trip_id}/hotels/{hotel_id}/select", response_model=list[HotelCandidateOut])
async def select_hotel(
    trip_id: str,
    hotel_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[HotelCandidate]:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    _assert_owns(result.scalar_one_or_none(), current_user)

    hotels_result = await db.execute(
        select(HotelCandidate)
        .where(HotelCandidate.trip_id == trip_id)
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
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    trip_result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_owns(trip_result.scalar_one_or_none(), current_user)

    items_result = await db.execute(
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
    )
    items = list(items_result.scalars().all())

    ics_content = _build_ics(trip, items)
    filename = f"travelos-{trip.destination_city.lower().replace(' ', '-')}.ics"
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Weather ───────────────────────────────────────────────────────────────────


@router.get("/{trip_id}/weather", response_model=list[WeatherDay])
async def get_trip_weather(
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[WeatherDay]:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_owns(result.scalar_one_or_none(), current_user)

    lat, lng = trip.latitude, trip.longitude
    if lat is None or lng is None:
        geo = await geocode(f"{trip.destination_city}, {trip.destination_country or ''}")
        if geo is None:
            return []
        lat, lng = geo.lat, geo.lng

    return await fetch_weather(lat, lng, trip.start_date, trip.end_date)


# ── Share ─────────────────────────────────────────────────────────────────────


@router.post("/{trip_id}/share", response_model=TripOut)
async def create_share_link(
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_owns(result.scalar_one_or_none(), current_user)

    trip.share_token = str(uuid.uuid4())
    trip.share_expires_at = datetime.now(UTC) + timedelta(days=30)
    await db.commit()
    await db.refresh(trip)
    return trip
