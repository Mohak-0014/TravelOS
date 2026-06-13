from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_active_user
from backend.db.base import get_db
from backend.db.models import Approval, ItineraryItem, Trip, User
from backend.db.schemas import ApprovalCreate, ApprovalDecision, ApprovalOut

router = APIRouter(tags=["approvals"])


def _assert_trip_owned(trip: Trip | None, user: User) -> Trip:
    if trip is None or trip.user_id != user.id:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Trip not found."}
        )
    return trip


@router.post(
    "/api/v1/trips/{trip_id}/approvals",
    response_model=ApprovalOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_approval(
    trip_id: str,
    body: ApprovalCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Approval:
    trip_result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = _assert_trip_owned(trip_result.scalar_one_or_none(), current_user)

    item_result = await db.execute(
        select(ItineraryItem).where(
            ItineraryItem.id == body.item_id,
            ItineraryItem.trip_id == trip_id,
        )
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Itinerary item not found."}
        )

    summary = f'Day {item.day_number}: Replace "{item.title}" with "{body.replacement_title}"'
    if body.reason:
        summary += f". Reason: {body.reason}"

    approval = Approval(
        trip_id=trip_id,
        proposed_by="user",
        change_type="user_replace",
        summary=summary,
        payload={
            "item_id": body.item_id,
            "day": item.day_number,
            "current": {"id": str(item.id), "title": item.title},
            "replacement": {"title": body.replacement_title},
            "reason": body.reason or "",
        },
        status="pending",
    )
    db.add(approval)
    trip.status = "awaiting_approval"
    await db.commit()
    await db.refresh(approval)
    return approval


@router.get("/api/v1/trips/{trip_id}/approvals", response_model=list[ApprovalOut])
async def list_approvals(
    trip_id: str,
    status: str | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[Approval]:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    _assert_trip_owned(result.scalar_one_or_none(), current_user)

    query = select(Approval).where(Approval.trip_id == trip_id)
    if status:
        query = query.where(Approval.status == status)
    query = query.order_by(Approval.created_at.desc())

    approvals = await db.execute(query)
    return list(approvals.scalars().all())


@router.get("/api/v1/approvals/{approval_id}", response_model=ApprovalOut)
async def get_approval(
    approval_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Approval:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found."}
        )

    # Verify ownership via trip
    trip_result = await db.execute(select(Trip).where(Trip.id == approval.trip_id))
    _assert_trip_owned(trip_result.scalar_one_or_none(), current_user)

    return approval


@router.post("/api/v1/approvals/{approval_id}")
async def resolve_approval(
    approval_id: str,
    body: ApprovalDecision,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found."}
        )

    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "message": "Approval is no longer pending."},
        )

    # Verify ownership
    trip_result = await db.execute(select(Trip).where(Trip.id == approval.trip_id))
    _assert_trip_owned(trip_result.scalar_one_or_none(), current_user)

    if body.decision not in ("approved", "rejected"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "decision must be 'approved' or 'rejected'.",
            },
        )

    approval.status = body.decision
    approval.resolved_at = datetime.now(UTC)
    await db.flush()

    # Restore trip status to "planned" once all approvals are resolved
    remaining = await db.execute(
        select(Approval).where(
            Approval.trip_id == approval.trip_id,
            Approval.status == "pending",
        )
    )
    if not remaining.scalars().all():
        trip_result2 = await db.execute(select(Trip).where(Trip.id == approval.trip_id))
        trip2 = trip_result2.scalar_one_or_none()
        if trip2 is not None and trip2.status == "awaiting_approval":
            trip2.status = "planned"

    await db.commit()
    await db.refresh(approval)

    return {"id": approval.id, "status": approval.status}
