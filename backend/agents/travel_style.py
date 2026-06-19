"""Travel Style agent — loads user preferences and synthesizes a structured travel profile."""

from __future__ import annotations

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from backend.agents._llm import build_llm
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import Preference, Trip
from backend.graphs.state import TravelOSState
from backend.memory.embeddings import embed_text, preference_text
from backend.memory.semantic import get_qdrant_client, search_feedback, search_trip_memories

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are the Travel Style Agent for TravelOS, an AI travel planning system.
Analyze the traveler's preferences and destination context, then produce a structured travel profile
that will guide the Itinerary Planner in building a personalized day-by-day plan.

Respond ONLY with valid JSON (no other text):
{
  "travel_style_summary": "2-3 sentence description of the traveler's style and goals",
  "style_tags": ["tag1", "tag2"],
  "accommodation_preference": "description of ideal accommodation type and location",
  "activity_preference": "description of preferred activity types and intensity",
  "dining_preference": "description of dining style and any dietary needs",
  "daily_rhythm": "preferred schedule density — how many activities per day and at what pace",
  "budget_priority": "how the traveler wants to allocate their budget across categories"
}

Valid style tags: culture, history, adventure, food, nature, nightlife, art, shopping,
relaxation, sports, family_friendly, luxury, budget_conscious, solo, couple, group,
moderate_pace, fast_pace, slow_pace, off_beaten_path, popular_attractions."""


def _build_llm() -> BaseChatModel:
    return build_llm("large", temperature=0.3)


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    user_id = state.get("user_id", "unknown")

    logger.info("travel_style_start", trip_id=trip_id, user_id=user_id)

    trip, pref = await _load_db_context(trip_id, user_id)
    prefs_dict = _preference_to_dict(pref)
    trip_context = _trip_to_context(trip)

    # Fetch past trips and approval feedback to personalise the profile
    embedding_hits = await _search_past_trips(user_id, prefs_dict)
    feedback_hits = await _search_feedback(user_id, prefs_dict, trip_context)

    profile = await _synthesize_profile(
        prefs_dict, trip_context, state.get("traveler_profiles", []), embedding_hits, feedback_hits
    )

    logger.info(
        "travel_style_complete",
        trip_id=trip_id,
        style_tags=profile.get("style_tags"),
        embedding_hits=len(embedding_hits),
        feedback_hits=len(feedback_hits),
    )

    updates: dict = {  # type: ignore[type-arg]
        "memory_context": {
            "preferences": prefs_dict,
            "travel_style_profile": profile,
            "embedding_hits": embedding_hits,
            "past_trips": embedding_hits,
        },
        "agent_messages": [
            SystemMessage(
                content=(
                    f"Travel Style: profile synthesized for trip={trip_id}. "
                    f"Tags: {profile.get('style_tags', [])}"
                )
            )
        ],
    }

    # Backfill budget_state.total from Trip when the supervisor left it as None
    existing_budget = state.get("budget_state") or {}
    if trip is not None and existing_budget.get("total") is None:
        updates["budget_state"] = {
            **existing_budget,
            "total": float(trip.budget_total) if trip.budget_total is not None else None,
            "currency": trip.budget_currency,
        }

    return updates


async def _load_db_context(trip_id: str, user_id: str) -> tuple[Trip | None, Preference | None]:
    try:
        async with AsyncSessionLocal() as session:
            trip_result = await session.execute(select(Trip).where(Trip.id == trip_id))
            trip = trip_result.scalar_one_or_none()

            pref_result = await session.execute(
                select(Preference).where(Preference.user_id == user_id)
            )
            pref = pref_result.scalar_one_or_none()

        if trip is None:
            logger.warning("travel_style_trip_not_found", trip_id=trip_id)
        if pref is None:
            logger.warning("travel_style_pref_not_found", user_id=user_id)

        return trip, pref
    except Exception as exc:
        logger.error("travel_style_db_error", trip_id=trip_id, error=str(exc))
        return None, None


def _preference_to_dict(pref: Preference | None) -> dict:  # type: ignore[type-arg]
    if pref is None:
        return {}
    return {
        "pace": pref.pace,
        "luxury_tier": pref.luxury_tier,
        "walking_tolerance": pref.walking_tolerance,
        "food_prefs": pref.food_prefs or [],
        "interests": pref.interests or [],
        "budget_behavior": pref.budget_behavior,
    }


def _trip_to_context(trip: Trip | None) -> str:
    if trip is None:
        return "Destination: unknown. Dates: unknown. Budget: unspecified."

    duration = (trip.end_date - trip.start_date).days + 1
    budget_str = (
        f"{trip.budget_total} {trip.budget_currency}"
        if trip.budget_total is not None
        else "unspecified"
    )
    country_part = f", {trip.destination_country}" if trip.destination_country else ""
    return (
        f"Destination: {trip.destination_city}{country_part}. "
        f"Dates: {trip.start_date} to {trip.end_date} ({duration} days). "
        f"Travelers: {trip.num_travelers}. Total budget: {budget_str}."
    )


async def _synthesize_profile(
    prefs: dict,  # type: ignore[type-arg]
    trip_context: str,
    traveler_profiles: list[dict],  # type: ignore[type-arg]
    past_trips: list[dict],  # type: ignore[type-arg]
    feedback_hits: list[dict] | None = None,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    prefs_str = (
        json.dumps(prefs) if prefs else "No preferences set — assume versatile moderate traveler."
    )
    profiles_str = (
        f"\nTraveler details: {json.dumps(traveler_profiles)}" if traveler_profiles else ""
    )

    past_trips_str = ""
    if past_trips:
        summaries: list[str] = []
        for pt in past_trips[:3]:
            city = pt.get("destination_city", "")
            country = pt.get("destination_country", "")
            tags = pt.get("style_tags") or []
            loc = f"{city}, {country}" if country else city
            tag_str = f" (style: {', '.join(tags[:3])})" if tags else ""
            summaries.append(f"- {loc}{tag_str}")
        past_trips_str = (
            "\nPast trips (use to personalise the profile — avoid repeating the same activities):\n"
            + "\n".join(summaries)
        )

    feedback_str = ""
    if feedback_hits:
        rejected = [f for f in feedback_hits if f.get("decision") == "rejected"]
        accepted = [f for f in feedback_hits if f.get("decision") == "approved"]
        lines: list[str] = []
        if rejected:
            lines.append(
                "Previously REJECTED (avoid similar suggestions): "
                + "; ".join(f["summary"][:70] for f in rejected[:4])
            )
        if accepted:
            lines.append(
                "Previously ACCEPTED (user welcomed these): "
                + "; ".join(f["summary"][:70] for f in accepted[:4])
            )
        if lines:
            feedback_str = (
                "\nUser approval history (respect rejections, reinforce acceptances):\n"
                + "\n".join(lines)
            )

    user_message = (
        f"Trip context: {trip_context}\n"
        f"User preferences: {prefs_str}"
        f"{profiles_str}"
        f"{past_trips_str}"
        f"{feedback_str}"
    )

    try:
        llm = _build_llm()
        response = await llm.ainvoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        )
        raw = str(response.content) if hasattr(response, "content") else str(response)
        return _parse_profile(raw)
    except Exception as exc:
        logger.error("travel_style_llm_error", error=str(exc))
        return _default_profile()


def _parse_profile(raw: str) -> dict:  # type: ignore[type-arg]
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        pass
    logger.warning("travel_style_parse_failed", raw_preview=raw[:200])
    return _default_profile()


def _default_profile() -> dict:  # type: ignore[type-arg]
    return {
        "travel_style_summary": (
            "A versatile traveler open to varied experiences with a moderate pace. "
            "Interested in local culture and cuisine."
        ),
        "style_tags": ["culture", "food", "moderate_pace"],
        "accommodation_preference": "Comfortable mid-range hotels in convenient locations",
        "activity_preference": "A mix of popular attractions and local experiences",
        "dining_preference": "Local cuisine with a mix of price ranges",
        "daily_rhythm": "2-3 activities per day with time to explore freely",
        "budget_priority": "Balanced spending across accommodation, food, and activities",
    }


async def _search_past_trips(
    user_id: str,
    prefs: dict,  # type: ignore[type-arg]
) -> list[dict]:  # type: ignore[type-arg]
    """
    Embed the current preference text and search Qdrant trip_memories for similar past trips.
    Degrades gracefully to [] when Qdrant is unavailable or no trips exist yet.
    """
    if not prefs:
        return []
    try:
        text = preference_text(prefs)
        vector = embed_text(text)
        client = get_qdrant_client()
        try:
            hits = await search_trip_memories(client, vector, user_id, limit=5)
        finally:
            await client.close()
        return hits
    except Exception as exc:
        logger.warning("travel_style_embedding_search_failed", user_id=user_id, error=str(exc))
        return []


async def _search_feedback(
    user_id: str,
    prefs: dict,  # type: ignore[type-arg]
    trip_context: str,
) -> list[dict]:  # type: ignore[type-arg]
    """
    Embed the current trip context and search Qdrant user_feedback for semantically similar
    past approve/reject decisions from this user.
    Degrades gracefully to [] when Qdrant is unavailable or no feedback exists yet.
    """
    try:
        prefs_str = preference_text(prefs) if prefs else "unspecified preferences"
        query = f"{trip_context} {prefs_str}"
        vector = embed_text(query)
        client = get_qdrant_client()
        try:
            hits = await search_feedback(client, vector, user_id, limit=8)
        finally:
            await client.close()
        return hits
    except Exception as exc:
        logger.warning("travel_style_feedback_search_failed", user_id=user_id, error=str(exc))
        return []
