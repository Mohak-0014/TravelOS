from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_active_user
from backend.db.base import get_db
from backend.db.models import ItineraryItem, Trip, TravelerProfile, User
from backend.db.schemas import (
    ItineraryItemCreate,
    ItineraryItemOut,
    ItineraryItemUpdate,
    TripCreate,
    TripOut,
    TripUpdate,
)
from backend.tools.geocode import geocode

router = APIRouter(prefix="/api/v1/trips", tags=["trips"])


def _assert_owns(trip: Trip | None, user: User) -> Trip:
    if trip is None or trip.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Trip not found."})
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

    # Geocode destination — best-effort, trip still created if Nominatim is unavailable
    geo = await geocode(f"{body.destination_city}, {body.destination_country or ''}")

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
        select(ItineraryItem).where(
            ItineraryItem.id == item_id, ItineraryItem.trip_id == trip_id
        )
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found."})

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
        select(ItineraryItem).where(
            ItineraryItem.id == item_id, ItineraryItem.trip_id == trip_id
        )
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found."})

    await db.delete(item)
    await db.commit()


@router.post("/{trip_id}/itinerary/generate")
async def generate_itinerary(
    trip_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    _assert_owns(result.scalar_one_or_none(), current_user)
    return {"status": "not_implemented"}
