"""Hotel agent — searches, scores, and selects hotels using Haiku for fast ranking."""

from __future__ import annotations

import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import delete, select

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import HotelCandidate, Trip
from backend.graphs.state import TravelOSState
from backend.tools import get_redis_client
from backend.tools.hotels import HotelOffer, search_hotels

logger = get_logger(__name__)

# Stars expected per luxury tier — used for deterministic scoring
_TIER_TARGET_STARS: dict[str, float] = {
    "budget": 2.0,
    "mid": 3.5,
    "luxury": 4.5,
}

# Fraction of total budget allocated to lodging for per-night budget calculation
_LODGING_BUDGET_FRACTION = 0.35

_SELECTION_SYSTEM = """You are the Hotel Selection Agent for TravelOS.
Given a list of hotel candidates and a traveler profile, choose the single best hotel.

Respond ONLY with valid JSON (no other text):
{
  "selected_index": 0,
  "rationale": "one sentence explaining why this hotel is the best match"
}

selected_index is the 0-based position in the candidates list."""


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(  # type: ignore[call-arg]
        model="claude-haiku-4-5-20251001",
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=256,
        temperature=0,
    )


# ── Entry point ───────────────────────────────────────────────────────────────


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    logger.info("hotel_agent_start", trip_id=trip_id)

    trip = await _load_trip(trip_id)
    if trip is None:
        logger.error("hotel_agent_trip_not_found", trip_id=trip_id)
        return {
            "hotel_state": {"candidates": [], "selected": None},
            "agent_messages": [
                SystemMessage(
                    content=f"Hotel Agent: trip {trip_id} not found — skipping hotel search."
                )
            ],
        }

    redis = get_redis_client()
    offers = await search_hotels(
        destination=trip.destination_city,
        check_in=trip.start_date,
        check_out=trip.end_date,
        guests=trip.num_travelers,
        cache=redis,
    )
    await redis.aclose()

    if not offers:
        logger.warning("hotel_agent_no_offers", trip_id=trip_id)
        return {
            "hotel_state": {"candidates": [], "selected": None},
            "agent_messages": [
                SystemMessage(
                    content=f"Hotel Agent: no hotel offers found for {trip.destination_city}."
                )
            ],
        }

    style_profile = (state.get("memory_context") or {}).get("travel_style_profile", {})
    budget_state = state.get("budget_state") or {}
    trip_nights = (trip.end_date - trip.start_date).days or 1

    ranked = _rank_offers(offers, style_profile, budget_state, trip_nights)
    top = ranked[:10]

    selected_idx = await _select_with_llm(top, style_profile, trip)
    selected = top[selected_idx] if top else None

    await _persist_candidates(trip_id, top, selected_idx if selected else None)

    logger.info(
        "hotel_agent_complete",
        trip_id=trip_id,
        candidates=len(top),
        selected=selected.name if selected else None,
    )

    return {
        "hotel_state": {
            "candidates": [_offer_to_dict(o) for o in top],
            "selected": _offer_to_dict(selected) if selected else None,
        },
        "agent_messages": [
            SystemMessage(
                content=(
                    f"Hotel Agent: {len(top)} candidates found for {trip.destination_city}. "
                    f"Selected: {selected.name if selected else 'none'}."
                )
            )
        ],
    }


# ── Scoring & ranking ─────────────────────────────────────────────────────────


def _rank_offers(
    offers: list[HotelOffer],
    style_profile: dict,  # type: ignore[type-arg]
    budget_state: dict,  # type: ignore[type-arg]
    trip_nights: int,
) -> list[HotelOffer]:
    luxury_tier = style_profile.get("accommodation_preference", "")
    # Infer tier from accommodation_preference text if explicit key absent
    inferred_tier = _infer_tier(luxury_tier)

    budget_per_night = _compute_budget_per_night(budget_state, trip_nights)

    scored: list[tuple[float, HotelOffer]] = []
    for offer in offers:
        score = _score_offer(offer, inferred_tier, budget_per_night)
        scored.append((score, offer))

    scored.sort(key=lambda x: x[0], reverse=True)
    ranked = [offer for _, offer in scored]
    # Attach match_score to each offer so it can be persisted
    for (score, _offer), ranked_offer in zip(scored, ranked, strict=False):
        ranked_offer.raw_payload["_match_score"] = round(score, 3)
    return ranked


def _infer_tier(accommodation_pref: str) -> str:
    low = accommodation_pref.lower()
    if any(w in low for w in ("luxury", "5-star", "five star", "boutique")):
        return "luxury"
    if any(w in low for w in ("budget", "hostel", "cheap", "1-star", "2-star")):
        return "budget"
    return "mid"


def _compute_budget_per_night(
    budget_state: dict,  # type: ignore[type-arg]
    trip_nights: int,
) -> float | None:
    total = budget_state.get("total")
    if not total:
        return None
    return float(total) * _LODGING_BUDGET_FRACTION / trip_nights


def _score_offer(
    offer: HotelOffer,
    luxury_tier: str,
    budget_per_night: float | None,
) -> float:
    return (
        _price_score(offer, budget_per_night)
        + _star_score(offer, luxury_tier)
        + _completeness_score(offer)
    )


def _price_score(offer: HotelOffer, budget_per_night: float | None) -> float:
    """0.0 – 0.4: how well the nightly rate fits the budget."""
    if offer.price_per_night is None or budget_per_night is None:
        return 0.2  # neutral when data is missing
    ratio = offer.price_per_night / budget_per_night
    if ratio <= 0.8:
        return 0.4  # great value
    if ratio <= 1.0:
        return 0.3  # within budget
    if ratio <= 1.2:
        return 0.15  # slightly over
    return 0.0  # clearly over budget


def _star_score(offer: HotelOffer, luxury_tier: str) -> float:
    """0.0 – 0.4: how well star rating matches the tier preference."""
    if offer.star_rating is None:
        return 0.15  # partial credit for unknown
    target = _TIER_TARGET_STARS.get(luxury_tier, 3.5)
    diff = abs(float(offer.star_rating) - target)
    return max(0.0, 0.4 * (1.0 - diff / 3.0))


def _completeness_score(offer: HotelOffer) -> float:
    """0.0 – 0.2: bonus for having image and coordinates."""
    score = 0.0
    if offer.image_url:
        score += 0.1
    if offer.lat is not None and offer.lng is not None:
        score += 0.1
    return score


# ── LLM selection ─────────────────────────────────────────────────────────────


async def _select_with_llm(
    candidates: list[HotelOffer],
    style_profile: dict,  # type: ignore[type-arg]
    trip: Trip,
) -> int:
    """Return 0-based index of best hotel; falls back to 0 on any error."""
    if not candidates:
        return 0

    candidates_summary = "\n".join(
        f"{i}. {o.name} — {o.star_rating or '?'}★, "
        f"${o.price_per_night or '?'}/night ({o.source_provider})"
        for i, o in enumerate(candidates)
    )

    trip_nights = (trip.end_date - trip.start_date).days or 1
    user_msg = (
        f"Trip: {trip.destination_city}, {trip_nights} nights, {trip.num_travelers} traveler(s).\n"
        f"Traveler style: {style_profile.get('travel_style_summary', 'moderate traveler')}\n"
        f"Accommodation preference: {style_profile.get('accommodation_preference', 'comfortable mid-range')}\n\n"  # noqa: E501
        f"Candidates:\n{candidates_summary}"
    )

    try:
        llm = _build_llm()
        response = await llm.ainvoke(
            [SystemMessage(content=_SELECTION_SYSTEM), HumanMessage(content=user_msg)]
        )
        raw = str(response.content) if hasattr(response, "content") else str(response)
        return _parse_selection(raw, len(candidates))
    except Exception as exc:
        logger.error("hotel_agent_llm_error", error=str(exc))
        return 0


def _parse_selection(raw: str, n_candidates: int) -> int:
    """Extract selected_index from Haiku JSON; clamp to valid range; fallback to 0."""
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            idx = int(data.get("selected_index", 0))
            return max(0, min(idx, n_candidates - 1))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return 0


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _load_trip(trip_id: str) -> Trip | None:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Trip).where(Trip.id == trip_id))
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("hotel_agent_db_load_error", trip_id=trip_id, error=str(exc))
        return None


async def _persist_candidates(
    trip_id: str,
    candidates: list[HotelOffer],
    selected_idx: int | None,
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(HotelCandidate).where(HotelCandidate.trip_id == trip_id))
            for i, offer in enumerate(candidates):
                match_score = offer.raw_payload.get("_match_score")
                session.add(
                    HotelCandidate(
                        trip_id=trip_id,
                        provider=offer.source_provider,
                        provider_hotel_id=offer.hotel_id,
                        name=offer.name,
                        star_rating=offer.star_rating,
                        latitude=offer.lat,
                        longitude=offer.lng,
                        image_url=offer.image_url,
                        price_total=offer.price_total,
                        price_currency=offer.price_currency,
                        price_per_night=offer.price_per_night,
                        meal_plan=offer.meal_plan,
                        refundable=offer.refundable,
                        booking_ref=offer.booking_ref,
                        match_score=match_score,
                        is_selected=(i == selected_idx),
                        raw_payload={
                            k: v for k, v in offer.raw_payload.items() if not k.startswith("_")
                        },
                    )
                )
            await session.commit()
            logger.info("hotel_candidates_persisted", trip_id=trip_id, count=len(candidates))
    except Exception as exc:
        logger.error("hotel_persist_failed", trip_id=trip_id, error=str(exc))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _offer_to_dict(offer: HotelOffer) -> dict:  # type: ignore[type-arg]
    d = offer.model_dump()
    # Strip internal scoring key before exposing to state
    d.get("raw_payload", {}).pop("_match_score", None)
    return d
