from fastapi import APIRouter, Depends, Request

from backend.agents import concierge as concierge_agent
from backend.api.dependencies import get_current_active_user, get_owned_trip
from backend.api.rate_limit import limiter
from backend.db.models import User
from backend.db.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["concierge"])


@router.post(
    "/api/v1/trips/{trip_id}/chat",
    response_model=ChatResponse,
    dependencies=[Depends(get_owned_trip)],  # 404s unless the caller owns the trip
)
@limiter.limit("20/minute")  # full LLM agent call — cap per-IP token spend
async def chat(
    request: Request,
    trip_id: str,
    body: ChatRequest,
    current_user: User = Depends(get_current_active_user),
) -> ChatResponse:
    response = await concierge_agent.ask(
        trip_id=trip_id,
        user_id=current_user.id,
        question=body.question,
    )
    return ChatResponse(
        answer=response.answer,
        sources=response.sources,
        proposal_id=response.proposal_id,
    )
