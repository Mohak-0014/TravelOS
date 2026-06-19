from datetime import UTC, date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_active_user
from backend.core.logging import get_logger
from backend.db.base import get_db
from backend.db.models import Approval, ItineraryItem, Trip, User, UserFeedback
from backend.db.schemas import ApprovalCreate, ApprovalDecision, ApprovalOut

logger = get_logger(__name__)

router = APIRouter(tags=["approvals"])


def _extract_context_tags(change_type: str, payload: dict) -> list[str]:  # type: ignore[type-arg]
    """Pull semantic labels from an approval payload for feedback embedding."""
    tags: list[str] = [change_type]
    current = payload.get("current")
    if isinstance(current, dict) and current.get("title"):
        tags.append(current["title"])
    for key in ("title", "event_name", "category"):
        val = payload.get(key)
        if val and isinstance(val, str):
            tags.append(val)
    return [t for t in dict.fromkeys(tags) if t]  # deduplicate, preserve order


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

    # Apply the item change when approved
    if body.decision == "approved" and approval.change_type in (
        "user_replace",
        "concierge_swap",
        "budget_swap",
    ):
        item_id = approval.payload.get("item_id")
        if item_id:
            item_result = await db.execute(select(ItineraryItem).where(ItineraryItem.id == item_id))
            item = item_result.scalar_one_or_none()
            if item is not None:
                replacement = approval.payload.get("replacement", {})
                item.title = replacement.get("title", item.title)
                desc = replacement.get("description")
                if desc:
                    item.description = desc

    elif body.decision == "approved" and approval.change_type == "concierge_add":
        payload = approval.payload
        day_number = int(payload.get("day", 1))

        existing = await db.execute(
            select(ItineraryItem).where(
                ItineraryItem.trip_id == approval.trip_id,
                ItineraryItem.day_number == day_number,
            )
        )
        day_items = existing.scalars().all()
        next_sort = max((i.sort_order for i in day_items), default=-1) + 1
        item_date = day_items[0].item_date if day_items else None

        db.add(
            ItineraryItem(
                trip_id=approval.trip_id,
                day_number=day_number,
                item_date=item_date,
                item_type="activity",
                title=payload.get("title", "New Activity"),
                description=payload.get("description") or None,
                is_outdoor=False,
                sort_order=next_sort,
            )
        )

    elif body.decision == "approved" and approval.change_type == "event_add":
        payload = approval.payload
        event_date_str = payload.get("event_date")
        day_number = payload.get("day_number", 1)

        # Parse event_date and optional start_time from payload
        try:
            event_date = date.fromisoformat(event_date_str) if event_date_str else None
        except (ValueError, TypeError):
            event_date = None

        start_time: time | None = None
        raw_time = payload.get("start_time")
        if raw_time:
            try:
                start_time = time.fromisoformat(raw_time)
            except (ValueError, TypeError):
                pass

        if event_date is not None:
            # Determine sort_order: place event at end of that day's items
            existing = await db.execute(
                select(ItineraryItem).where(
                    ItineraryItem.trip_id == approval.trip_id,
                    ItineraryItem.day_number == day_number,
                )
            )
            day_items = existing.scalars().all()
            next_sort = max((i.sort_order for i in day_items), default=-1) + 1

            price_min = payload.get("price_min")
            new_item = ItineraryItem(
                trip_id=approval.trip_id,
                day_number=day_number,
                item_date=event_date,
                start_time=start_time,
                item_type="activity",
                title=payload.get("event_name", "Event"),
                description=(
                    f"{payload.get('category', '')} at {payload.get('venue_name', '')}. "
                    f"Tickets: {payload.get('url', '')}"
                ).strip(),
                latitude=payload.get("lat"),
                longitude=payload.get("lng"),
                source_provider=payload.get("source"),
                source_ref=payload.get("url"),
                est_cost=float(price_min) if price_min is not None else None,
                est_cost_currency=payload.get("price_currency"),
                is_outdoor=False,
                sort_order=next_sort,
            )
            db.add(new_item)

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

    # Record feedback for the learning loop
    try:
        context_tags = _extract_context_tags(approval.change_type, approval.payload or {})
        feedback = UserFeedback(
            user_id=str(current_user.id),
            trip_id=str(approval.trip_id),
            approval_id=str(approval.id),
            change_type=approval.change_type,
            decision=body.decision,
            context_tags=context_tags,
            summary=approval.summary or "",
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)

        # Embed the feedback vector in Celery (CPU-heavy — never in request path)
        from backend.workflows.celery_tasks import embed_feedback_async  # noqa: PLC0415

        embed_feedback_async.delay(str(feedback.id))
    except Exception as exc:
        logger.warning("feedback_write_failed", approval_id=approval_id, error=str(exc))

    return {"id": approval.id, "status": approval.status}
