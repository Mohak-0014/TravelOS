from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents import concierge as concierge_agent
from backend.api.dependencies import get_current_active_user
from backend.db.base import get_db
from backend.db.models import Trip, User
from backend.db.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["concierge"])


@router.post("/api/v1/trips/{trip_id}/chat", response_model=ChatResponse)
async def chat(
    trip_id: str,
    body: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if trip is None or trip.user_id != current_user.id:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Trip not found."}
        )

    response = await concierge_agent.ask(
        trip_id=trip_id,
        user_id=current_user.id,
        question=body.question,
    )
    return ChatResponse(answer=response.answer, sources=response.sources)
