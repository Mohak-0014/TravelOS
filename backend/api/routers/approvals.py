from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_active_user
from backend.db.base import get_db
from backend.db.models import Approval, Trip, User
from backend.db.schemas import ApprovalDecision, ApprovalOut

router = APIRouter(tags=["approvals"])


def _assert_trip_owned(trip: Trip | None, user: User) -> Trip:
    if trip is None or trip.user_id != user.id:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Trip not found."}
        )
    return trip


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

    # Stub: update status only — full mutation logic wired in Week 9
    from datetime import datetime

    approval.status = body.decision
    approval.resolved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(approval)

    return {"id": approval.id, "status": approval.status}
