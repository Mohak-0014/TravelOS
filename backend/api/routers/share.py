"""Public share endpoint — no auth required."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.rate_limit import limiter
from backend.db.base import get_db
from backend.db.models import ItineraryItem, Trip
from backend.db.schemas import ItineraryItemOut, ShareTripOut

router = APIRouter(prefix="/api/v1/share", tags=["share"])


@router.get("/{token}", response_model=ShareTripOut)
@limiter.limit("30/minute")  # public + unauthenticated — cap scraping/replay
async def get_shared_trip(
    request: Request, token: str, db: AsyncSession = Depends(get_db)
) -> ShareTripOut:
    result = await db.execute(select(Trip).where(Trip.share_token == token))
    trip = result.scalar_one_or_none()

    if trip is None or trip.share_expires_at is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Share link not found."}
        )

    expires = trip.share_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise HTTPException(
            status_code=410, detail={"code": "EXPIRED", "message": "Share link has expired."}
        )

    items_result = await db.execute(
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip.id)
        .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
    )
    items = list(items_result.scalars().all())

    return ShareTripOut(
        id=trip.id,
        title=trip.title,
        destination_city=trip.destination_city,
        destination_country=trip.destination_country,
        start_date=trip.start_date,
        end_date=trip.end_date,
        num_travelers=trip.num_travelers,
        budget_currency=trip.budget_currency,
        packing_list=trip.packing_list,
        itinerary=[ItineraryItemOut.model_validate(it) for it in items],
    )
