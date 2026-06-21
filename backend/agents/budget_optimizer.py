"""Budget Optimizer agent — compares planned spend to budget_total and proposes adjustments."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from backend.agents._llm import build_llm
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import Approval, HotelCandidate, ItineraryItem, Trip
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)

_OVER_THRESHOLD = 0.15  # 15% over → propose swaps
_UNDER_THRESHOLD = -0.30  # 30% under → suggest upgrade
_MAX_SWAP_PROPOSALS = 3

_SWAP_SYSTEM = """You are a budget-conscious travel advisor.
A trip is over budget. Suggest a free or very cheap alternative to the given paid activity.
Respond ONLY with valid JSON — no other text:
{
  "title": "Alternative activity title",
  "description": "Brief description and why it is a good substitution",
  "reason": "Saves approximately X in budget"
}"""

_UPGRADE_SYSTEM = """You are a luxury travel advisor.
A trip is significantly under its budget. Suggest one premium upgrade.
Respond ONLY with valid JSON — no other text:
{
  "title": "Premium experience title",
  "description": "Brief description of the upgrade",
  "reason": "Uses remaining budget well"
}"""


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    logger.info("budget_optimizer_start", trip_id=trip_id)

    try:
        trip = await _load_trip(trip_id)
        if trip is None or not trip.budget_total:
            logger.info("budget_optimizer_skip", trip_id=trip_id, reason="no budget set")
            return _noop(state)

        budget_total = float(trip.budget_total)
        itinerary: list[dict] = list(state.get("itinerary") or [])  # type: ignore[arg-type]
        hotel_state: dict = dict(state.get("hotel_state") or {})  # type: ignore[type-arg]

        costs = _compute_costs(itinerary, hotel_state)
        total_planned = sum(costs.values())

        if total_planned == 0:
            logger.info("budget_optimizer_skip", trip_id=trip_id, reason="no cost data")
            return _noop(state)

        deviation = (total_planned - budget_total) / budget_total

        proposals: list[dict] = []  # type: ignore[type-arg]

        if deviation > _OVER_THRESHOLD:
            # Load items from DB so we have real UUIDs for on-approve lookup
            db_items = await _load_expensive_activities(trip_id, top_n=_MAX_SWAP_PROPOSALS)
            for item in db_items:
                p = await _propose_swap(trip, item, deviation, costs)
                if p:
                    proposals.append(p)

        elif deviation < _UNDER_THRESHOLD:
            # Well under budget — propose one premium upgrade
            p = await _propose_upgrade(trip, hotel_state, costs, deviation)
            if p:
                proposals.append(p)

        if proposals:
            await _persist_approvals(trip_id, proposals)
            await _set_trip_awaiting_approval(trip_id)

        status = (
            "over_budget"
            if deviation > _OVER_THRESHOLD
            else "under_budget"
            if deviation < _UNDER_THRESHOLD
            else "on_track"
        )

        budget_summary: dict = {  # type: ignore[type-arg]
            "by_category": costs,
            "total_planned": round(total_planned, 2),
            "budget_total": budget_total,
            "deviation_pct": round(deviation * 100, 1),
            "currency": trip.budget_currency,
            "status": status,
            "proposals_created": len(proposals),
        }

        # Merge with any existing budget_state (validation may have written estimated_planned)
        existing: dict = dict(state.get("budget_state") or {})  # type: ignore[type-arg]
        existing.update(budget_summary)

        sign = "+" if deviation >= 0 else ""
        summary = (
            f"Budget: {trip.budget_currency} {total_planned:.0f} planned"
            f" / {budget_total:.0f} total ({sign}{deviation * 100:.1f}%)."
            f" Status: {status}." + (f" {len(proposals)} proposal(s) created." if proposals else "")
        )

        logger.info(
            "budget_optimizer_complete",
            trip_id=trip_id,
            deviation_pct=round(deviation * 100, 1),
            status=status,
            proposals=len(proposals),
        )

        return {
            "budget_state": existing,
            "agent_messages": [SystemMessage(content=f"Budget Optimizer [{trip_id}]: {summary}")],
        }

    except Exception as exc:
        logger.error("budget_optimizer_failed", trip_id=trip_id, error=str(exc))
        return _noop(state)


# ── Cost calculation ──────────────────────────────────────────────────────────


def _compute_costs(itinerary: list[dict], hotel_state: dict) -> dict:  # type: ignore[type-arg]
    costs: dict[str, float] = {"lodging": 0.0, "activities": 0.0, "meals": 0.0, "transport": 0.0}

    selected = hotel_state.get("selected") or {}
    if isinstance(selected, dict):
        hotel_cost = float(selected.get("price_total") or 0)
        costs["lodging"] = round(hotel_cost, 2)

    for item in itinerary:
        raw_cost = item.get("est_cost")
        if not raw_cost:
            continue
        cost = float(raw_cost)
        if cost <= 0:
            continue
        itype = str(item.get("item_type") or "")
        if itype == "activity":
            costs["activities"] += cost
        elif itype == "meal":
            costs["meals"] += cost
        elif itype == "transport":
            costs["transport"] += cost

    return {k: round(v, 2) for k, v in costs.items()}


async def _load_expensive_activities(
    trip_id: str,
    top_n: int = 3,
) -> list[dict]:  # type: ignore[type-arg]
    """Load paid activity items from DB (with real UUIDs) sorted by cost desc."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ItineraryItem)
                .where(
                    ItineraryItem.trip_id == trip_id,
                    ItineraryItem.item_type == "activity",
                    ItineraryItem.est_cost > 0,
                )
                .order_by(ItineraryItem.est_cost.desc())
                .limit(top_n)
            )
            rows = result.scalars().all()
            return [
                {
                    "id": str(r.id),
                    "day_number": r.day_number,
                    "title": r.title,
                    "est_cost": float(r.est_cost),
                }
                for r in rows
            ]
    except Exception as exc:
        logger.error("budget_optimizer_load_items_error", trip_id=trip_id, error=str(exc))
        return []


# ── LLM proposal helpers ──────────────────────────────────────────────────────


async def _propose_swap(
    trip: Trip,
    item: dict,  # type: ignore[type-arg]
    deviation: float,
    costs: dict,  # type: ignore[type-arg]
) -> dict | None:  # type: ignore[type-arg]
    currency = trip.budget_currency
    cost = float(item.get("est_cost") or 0)
    prompt = (
        f"City: {trip.destination_city}\n"
        f"Paid activity: \"{item.get('title')}\" costs {currency} {cost:.0f}\n"
        f"Trip budget: {currency} {trip.budget_total:.0f}"
        f" ({deviation * 100:+.1f}% over budget)\n"
        f"By category — lodging: {costs['lodging']:.0f},"
        f" activities: {costs['activities']:.0f},"
        f" meals: {costs['meals']:.0f},"
        f" transport: {costs['transport']:.0f}\n"
        "Suggest a free or very cheap alternative activity."
    )
    raw = await _llm_json(prompt, _SWAP_SYSTEM)
    if raw is None or not raw.get("title"):
        return None

    return {
        "proposed_by": "budget_optimizer",
        "change_type": "budget_swap",
        "summary": (
            f"Day {item.get('day_number')}: Replace \"{item.get('title')}\""
            f" (est. {currency} {cost:.0f}) with \"{raw['title']}\" to reduce spend"
        ),
        "payload": {
            "item_id": str(item.get("id") or ""),
            "day": item.get("day_number"),
            "current": {"id": str(item.get("id") or ""), "title": item.get("title")},
            "replacement": {
                "title": raw["title"],
                "description": raw.get("description", ""),
            },
            "reason": raw.get("reason", "Saves budget"),
            "est_cost_original": cost,
            "currency": currency,
        },
    }


async def _propose_upgrade(
    trip: Trip,
    hotel_state: dict,  # type: ignore[type-arg]
    costs: dict,  # type: ignore[type-arg]
    deviation: float,
) -> dict | None:  # type: ignore[type-arg]
    currency = trip.budget_currency
    remaining = float(trip.budget_total) * abs(deviation)
    selected = hotel_state.get("selected") or {}
    hotel_name = selected.get("name", "current hotel") if isinstance(selected, dict) else "hotel"

    # Require a concrete DB candidate — text-only suggestions can't be applied on approve
    candidate = await _load_upgrade_candidate(str(trip.id), selected)
    if candidate is None:
        return None

    star_str = f" ({candidate['star_rating']:.0f}★)" if candidate.get("star_rating") else ""
    price_str = (
        f", {currency} {candidate['price_total']:.0f} total" if candidate.get("price_total") else ""
    )
    prompt = (
        f"City: {trip.destination_city}\n"
        f"Current hotel: {hotel_name}\n"
        f"Upgrade option: {candidate['name']}{star_str}{price_str}\n"
        f"Trip budget: {currency} {trip.budget_total:.0f}"
        f" (only {abs(deviation) * 100:.0f}% used — {remaining:.0f} remaining)\n"
        "In one sentence, explain why this hotel upgrade is worthwhile."
    )
    raw = await _llm_json(prompt, _UPGRADE_SYSTEM)
    if raw is None or not raw.get("title"):
        return None

    return {
        "proposed_by": "budget_optimizer",
        "change_type": "budget_upgrade",
        "summary": (
            f"Budget upgrade: switch to \"{candidate['name']}\""
            f" — trip is {abs(deviation) * 100:.0f}% under budget"
        ),
        "payload": {
            "candidate_id": candidate["id"],
            "title": candidate["name"],
            "description": raw.get("description", ""),
            "reason": raw.get("reason", "Uses remaining budget well"),
            "budget_remaining": round(remaining, 2),
            "currency": currency,
            "star_rating": candidate.get("star_rating"),
            "price_total": candidate.get("price_total"),
        },
    }


async def _load_upgrade_candidate(
    trip_id: str,
    selected: dict,  # type: ignore[type-arg]
) -> dict | None:  # type: ignore[type-arg]
    """Return the best non-selected HotelCandidate with a higher star rating than current."""
    try:
        current_stars = float(selected.get("star_rating") or 0)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(HotelCandidate)
                .where(
                    HotelCandidate.trip_id == trip_id,
                    HotelCandidate.is_selected.is_(False),
                )
                .order_by(HotelCandidate.star_rating.desc())
                .limit(5)
            )
            for c in result.scalars().all():
                if float(c.star_rating or 0) > current_stars:
                    return {
                        "id": str(c.id),
                        "name": c.name,
                        "star_rating": float(c.star_rating) if c.star_rating else None,
                        "price_total": float(c.price_total) if c.price_total else None,
                    }
    except Exception as exc:
        logger.error("budget_optimizer_candidate_load_error", trip_id=trip_id, error=str(exc))
    return None


async def _llm_json(
    prompt: str,
    system: str,
) -> dict | None:  # type: ignore[type-arg]
    try:
        llm = build_llm("small", temperature=0.3)
        response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        raw = str(getattr(response, "content", response)).strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            return parsed if isinstance(parsed, dict) else None
    except Exception as exc:
        logger.warning("budget_optimizer_llm_error", error=str(exc))
    return None


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _load_trip(trip_id: str) -> Trip | None:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Trip).where(Trip.id == trip_id))
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("budget_optimizer_trip_load_error", trip_id=trip_id, error=str(exc))
        return None


async def _persist_approvals(
    trip_id: str,
    proposals: list[dict],  # type: ignore[type-arg]
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            for p in proposals:
                session.add(
                    Approval(
                        trip_id=trip_id,
                        proposed_by=p["proposed_by"],
                        change_type=p["change_type"],
                        summary=p["summary"],
                        payload=p["payload"],
                        status="pending",
                    )
                )
            await session.commit()
        logger.info("budget_optimizer_approvals_persisted", trip_id=trip_id, count=len(proposals))
    except Exception as exc:
        logger.error("budget_optimizer_persist_error", trip_id=trip_id, error=str(exc))


async def _set_trip_awaiting_approval(trip_id: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            trip = await session.get(Trip, trip_id)
            if trip is not None:
                trip.status = "awaiting_approval"
                await session.commit()
    except Exception as exc:
        logger.error("budget_optimizer_status_error", trip_id=trip_id, error=str(exc))


def _noop(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    return {
        "budget_state": dict(state.get("budget_state") or {}),
        "agent_messages": [],
    }
