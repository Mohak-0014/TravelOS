"""Concierge agent — answers freeform user questions about their trip using grounded tool calls."""

from __future__ import annotations

import asyncio
import json
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.agents._llm import build_llm
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import Approval, HotelCandidate, ItineraryItem, Preference, Trip
from backend.memory.embeddings import embed_text
from backend.memory.semantic import get_qdrant_client, search_preferences, search_trip_memories
from backend.tools.places import search_attractions as _search_attractions
from backend.tools.restaurants import search_restaurants as _search_restaurants

logger = get_logger(__name__)

_MAX_TOOL_ROUNDS = 3


# ── Public response model ──────────────────────────────────────────────────────


class ConciergeResponse(BaseModel):
    answer: str
    sources: list[dict]  # type: ignore[type-arg]
    proposal_id: str | None = None


# ── Tool input schemas (class name becomes the tool name via bind_tools) ───────


class SearchAttractions(BaseModel):
    """Search tourist attractions, museums, landmarks, and points of interest near a location
    using OpenStreetMap. Call this when the user asks about sightseeing, things to do,
    places to visit, or any specific attraction."""

    lat: float = Field(description="Latitude of the search centre")
    lng: float = Field(description="Longitude of the search centre")
    radius_m: int = Field(default=2000, description="Search radius in metres (200–10 000)")


class SearchRestaurants(BaseModel):
    """Search restaurants and dining options near a location using Foursquare.
    Call this when the user asks about food, restaurants, cafes, or where to eat."""

    lat: float = Field(description="Latitude of the search centre")
    lng: float = Field(description="Longitude of the search centre")
    radius_m: int = Field(default=1000, description="Search radius in metres (200–5 000)")


class ProposeItineraryChange(BaseModel):
    """Propose replacing a specific itinerary item with an alternative. Use this when the
    user explicitly asks to swap, change, or replace an activity, meal, or venue on a specific
    day. This creates an approval request — the user will see a banner and must approve before
    any change is applied. Do NOT call this speculatively; only when the user clearly asks to
    make a change."""

    day: int = Field(description="Day number (1-indexed) of the item to replace")
    item_index: int = Field(
        description="0-indexed position of the item within that day (0 = first item)"
    )
    replacement_title: str = Field(description="Title of the replacement activity or venue")
    replacement_description: str = Field(
        description="Brief description of the replacement and why it fits the trip"
    )
    reason: str = Field(
        description="Why this replacement is better (e.g. 'rain forecast', 'user prefers indoor')"
    )


class ProposeAddItem(BaseModel):
    """Propose adding a brand-new activity, restaurant, or venue to a specific day. Use this
    when the user asks to ADD something to their plan (not replace an existing item). Creates
    an approval request — the user must approve before the item is inserted."""

    day: int = Field(description="Day number (1-indexed) to add the item to")
    title: str = Field(description="Title of the new activity or venue")
    description: str = Field(description="Brief description of the activity and why it fits")
    reason: str = Field(description="Why this addition suits the traveller's style or the trip")


_TOOL_SCHEMAS = [SearchAttractions, SearchRestaurants, ProposeItineraryChange, ProposeAddItem]

# Keywords that signal the user wants to add something to their plan
_ADD_RE = re.compile(r"\b(add|include|put|insert|schedule|book)\b", re.IGNORECASE)
# Keywords that signal the user wants to replace/swap something
_REPLACE_RE = re.compile(
    r"\b(replace|swap|change|switch|remove|cancel|drop|delete)\b", re.IGNORECASE
)
# Must also reference the plan/itinerary to avoid false positives
_PLAN_RE = re.compile(r"\b(day \d|day\d|plan|itinerary|schedule|trip|my trip)\b", re.IGNORECASE)


def _detect_mod_type(question: str) -> str | None:
    """Return 'add', 'replace', or None based on clear modification keywords."""
    if _ADD_RE.search(question) and _PLAN_RE.search(question):
        return "add"
    if _REPLACE_RE.search(question) and _PLAN_RE.search(question):
        return "replace"
    return None


# ── LLM ────────────────────────────────────────────────────────────────────────


def _build_llm() -> BaseChatModel:
    return build_llm("large", temperature=0.3)


# ── Main entry point ───────────────────────────────────────────────────────────


async def ask(trip_id: str, user_id: str, question: str) -> ConciergeResponse:
    """
    Answer a freeform question about the user's trip.

    Loads DB context (trip, itinerary, hotel, preferences) and past-trip memories from Qdrant,
    then runs a tool-use loop that can call SearchAttractions, SearchRestaurants, or
    ProposeItineraryChange. Degrades gracefully on any infrastructure failure.
    """
    logger.info("concierge_ask", trip_id=trip_id, question_len=len(question))

    try:
        trip, items, hotel = await _load_trip_context(trip_id, user_id)
        pref = await _load_preferences(user_id)
        memory = await _load_memory_context(user_id, question)

        system_prompt = _build_system_prompt(trip, items, hotel, pref, memory)

        # Detect modification intent and force the appropriate tool so the model can't refuse
        mod_type = _detect_mod_type(question)
        if mod_type == "add":
            llm = _build_llm().bind_tools([ProposeAddItem], tool_choice="any")
            logger.info("concierge_forced_tool", trip_id=trip_id, tool="ProposeAddItem")
        elif mod_type == "replace":
            llm = _build_llm().bind_tools([ProposeItineraryChange], tool_choice="any")
            logger.info("concierge_forced_tool", trip_id=trip_id, tool="ProposeItineraryChange")
        else:
            llm = _build_llm().bind_tools(_TOOL_SCHEMAS)

        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question),
        ]
        all_sources: list[dict[str, object]] = []
        proposal_id: str | None = None

        for _ in range(_MAX_TOOL_ROUNDS):
            response = await llm.ainvoke(messages)
            messages.append(response)

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                answer = _extract_text(response)
                logger.info("concierge_answered", trip_id=trip_id, sources=len(all_sources))
                return ConciergeResponse(
                    answer=answer, sources=all_sources, proposal_id=proposal_id
                )

            for tc in tool_calls:
                name: str = tc["name"]
                args: dict = tc.get("args") or {}  # type: ignore[type-arg]
                tc_id: str = tc.get("id") or ""
                result_text, sources, pid = await _run_tool(name, args, trip_id)
                all_sources.extend(sources)
                if pid is not None:
                    proposal_id = pid
                messages.append(ToolMessage(content=result_text, tool_call_id=tc_id))

            # After a modification tool call that created a proposal, break immediately
            # and synthesize with the unbound LLM — the forced llm would 400 on re-entry
            if proposal_id is not None:
                break

        # Synthesis — always uses unbound LLM (no tool_choice) so Groq won't reject it
        final = await _build_llm().ainvoke(messages)
        answer = _extract_text(final)
        logger.info("concierge_max_rounds_synthesis", trip_id=trip_id)
        return ConciergeResponse(answer=answer, sources=all_sources, proposal_id=proposal_id)

    except Exception as exc:
        logger.error("concierge_failed", trip_id=trip_id, error=str(exc))
        return ConciergeResponse(
            answer="I'm sorry, I couldn't process your question right now. Please try again.",
            sources=[],
        )


# ── Tool execution ─────────────────────────────────────────────────────────────


async def _run_tool(
    name: str,
    args: dict,  # type: ignore[type-arg]
    trip_id: str,
) -> tuple[str, list[dict], str | None]:  # type: ignore[type-arg]
    """Dispatch a tool call by name. Returns (result_json, sources, proposal_id_or_None)."""
    try:
        if name == "ProposeItineraryChange":
            result_text, pid = await _create_itinerary_change_proposal(trip_id, args)
            return result_text, [], pid

        if name == "ProposeAddItem":
            result_text, pid = await _create_add_item_proposal(trip_id, args)
            return result_text, [], pid

        lat = float(args.get("lat", 0.0))
        lng = float(args.get("lng", 0.0))

        if name == "SearchAttractions":
            radius = int(args.get("radius_m", 2000))
            places = await _search_attractions(lat, lng, radius)
            sources = [
                {"type": "attraction", "name": p.name, "lat": p.lat, "lng": p.lng, "kinds": p.kinds}
                for p in places
            ]
            result = json.dumps(
                [
                    {
                        "name": p.name,
                        "kinds": p.kinds,
                        "lat": p.lat,
                        "lng": p.lng,
                        "website": p.website,
                    }
                    for p in places
                ]
            )
            logger.info("concierge_tool_attractions", count=len(places))
            return result, sources, None

        if name == "SearchRestaurants":
            radius = int(args.get("radius_m", 1000))
            restaurants = await _search_restaurants(lat, lng, radius)
            sources = [
                {
                    "type": "restaurant",
                    "name": r.name,
                    "lat": r.lat,
                    "lng": r.lng,
                    "categories": r.categories,
                    "price_level": r.price_level,
                }
                for r in restaurants
            ]
            result = json.dumps(
                [
                    {
                        "name": r.name,
                        "categories": r.categories,
                        "price_level": r.price_level,
                        "address": r.address,
                        "lat": r.lat,
                        "lng": r.lng,
                    }
                    for r in restaurants
                ]
            )
            logger.info("concierge_tool_restaurants", count=len(restaurants))
            return result, sources, None

        logger.warning("concierge_unknown_tool", name=name)
    except Exception as exc:
        logger.warning("concierge_tool_error", name=name, error=str(exc))

    return json.dumps([]), [], None


async def _create_itinerary_change_proposal(
    trip_id: str,
    args: dict,  # type: ignore[type-arg]
) -> tuple[str, str | None]:
    """
    Create a pending Approval record for a concierge-proposed itinerary swap.
    Returns (result_json, approval_id_or_None).
    """
    try:
        day = int(args.get("day", 0))
        item_index = int(args.get("item_index", 0))
        replacement_title = str(args.get("replacement_title", ""))
        replacement_description = str(args.get("replacement_description", ""))
        reason = str(args.get("reason", ""))

        async with AsyncSessionLocal() as session:
            items_result = await session.execute(
                select(ItineraryItem)
                .where(ItineraryItem.trip_id == trip_id, ItineraryItem.day_number == day)
                .order_by(ItineraryItem.sort_order)
            )
            day_items = list(items_result.scalars().all())

            if not day_items or item_index < 0 or item_index >= len(day_items):
                return (
                    json.dumps(
                        {
                            "status": "error",
                            "reason": f"No item at day={day} index={item_index} "
                            f"({len(day_items)} items on that day)",
                        }
                    ),
                    None,
                )

            item = day_items[item_index]
            summary = f'Day {day}: Replace "{item.title}" with "{replacement_title}"'
            if reason:
                summary += f". {reason}"

            approval = Approval(
                trip_id=trip_id,
                proposed_by="concierge",
                change_type="concierge_swap",
                summary=summary,
                payload={
                    "item_id": str(item.id),
                    "day": day,
                    "current": {"id": str(item.id), "title": item.title},
                    "replacement": {
                        "title": replacement_title,
                        "description": replacement_description,
                    },
                    "reason": reason,
                },
                status="pending",
            )
            session.add(approval)

            trip_result = await session.execute(select(Trip).where(Trip.id == trip_id))
            trip = trip_result.scalar_one_or_none()
            if trip is not None:
                trip.status = "awaiting_approval"

            await session.commit()
            await session.refresh(approval)

        logger.info("concierge_proposal_created", trip_id=trip_id, approval_id=approval.id)
        return (
            json.dumps({"status": "proposed", "approval_id": approval.id, "summary": summary}),
            approval.id,
        )

    except Exception as exc:
        logger.error("concierge_proposal_failed", trip_id=trip_id, error=str(exc))
        return json.dumps({"status": "error", "reason": str(exc)}), None


async def _create_add_item_proposal(
    trip_id: str,
    args: dict,  # type: ignore[type-arg]
) -> tuple[str, str | None]:
    """Create a pending Approval record for a concierge-proposed new itinerary item."""
    try:
        day = int(args.get("day", 1))
        title = str(args.get("title", "")).strip()
        description = str(args.get("description", ""))
        reason = str(args.get("reason", ""))

        if not title:
            return json.dumps({"status": "error", "reason": "title is required"}), None

        async with AsyncSessionLocal() as session:
            trip_result = await session.execute(select(Trip).where(Trip.id == trip_id))
            trip = trip_result.scalar_one_or_none()
            if trip is None:
                return json.dumps({"status": "error", "reason": "trip not found"}), None

            summary = f'Day {day}: Add "{title}"'
            if reason:
                summary += f". {reason}"

            approval = Approval(
                trip_id=trip_id,
                proposed_by="concierge",
                change_type="concierge_add",
                summary=summary,
                payload={
                    "day": day,
                    "title": title,
                    "description": description,
                    "reason": reason,
                },
                status="pending",
            )
            session.add(approval)
            trip.status = "awaiting_approval"
            await session.commit()
            await session.refresh(approval)

        logger.info("concierge_add_proposed", trip_id=trip_id, approval_id=approval.id)
        return (
            json.dumps({"status": "proposed", "approval_id": str(approval.id), "summary": summary}),
            str(approval.id),
        )

    except Exception as exc:
        logger.error("concierge_add_proposal_failed", trip_id=trip_id, error=str(exc))
        return json.dumps({"status": "error", "reason": str(exc)}), None


# ── Context loading ────────────────────────────────────────────────────────────


async def _load_trip_context(
    trip_id: str,
    user_id: str,
) -> tuple[Trip | None, list[ItineraryItem], HotelCandidate | None]:
    try:
        async with AsyncSessionLocal() as session:
            trip_result = await session.execute(select(Trip).where(Trip.id == trip_id))
            trip = trip_result.scalar_one_or_none()

            if trip is None or trip.user_id != user_id:
                return None, [], None

            items_result = await session.execute(
                select(ItineraryItem)
                .where(ItineraryItem.trip_id == trip_id)
                .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
            )
            items = list(items_result.scalars().all())

            hotel_result = await session.execute(
                select(HotelCandidate).where(
                    HotelCandidate.trip_id == trip_id,
                    HotelCandidate.is_selected == True,  # noqa: E712
                )
            )
            hotel = hotel_result.scalar_one_or_none()

        return trip, items, hotel
    except Exception as exc:
        logger.error("concierge_trip_load_error", trip_id=trip_id, error=str(exc))
        return None, [], None


async def _load_preferences(user_id: str) -> Preference | None:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Preference).where(Preference.user_id == user_id))
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("concierge_pref_load_error", user_id=user_id, error=str(exc))
        return None


async def _load_memory_context(user_id: str, question: str) -> dict:  # type: ignore[type-arg]
    """
    Embed the question and search Qdrant for semantically similar past trips and preferences.
    The embedding runs in a thread pool so it does not block the async event loop.
    Degrades gracefully to empty lists when Qdrant is unavailable.
    """
    try:
        loop = asyncio.get_event_loop()
        vector: list[float] = await loop.run_in_executor(None, embed_text, question)

        client = get_qdrant_client()
        try:
            past_trips = await search_trip_memories(client, vector, user_id, limit=3)
            pref_hits = await search_preferences(client, vector, user_id, limit=1)
        finally:
            await client.close()

        return {"past_trips": past_trips, "pref_hits": pref_hits}
    except Exception as exc:
        logger.warning("concierge_memory_error", user_id=user_id, error=str(exc))
        return {"past_trips": [], "pref_hits": []}


# ── Prompt construction ────────────────────────────────────────────────────────


def _build_system_prompt(
    trip: Trip | None,
    items: list[ItineraryItem],
    hotel: HotelCandidate | None,
    pref: Preference | None,
    memory: dict,  # type: ignore[type-arg]
) -> str:
    lines = [
        "You are the TravelOS Concierge — a knowledgeable, friendly travel assistant.",
        "You help travelers answer questions about their specific trip.",
        "",
        "## Grounding rules (non-negotiable)",
        "- Never invent place names, addresses, prices, ratings, or opening hours.",
        "- If the user asks about restaurants or attractions, call the relevant tool first.",
        "- Only cite places returned by a tool or listed in the trip context below.",
        "- If tools return no results, say so honestly — do not fabricate alternatives.",
        "- You may answer directly (without calling a tool) for questions about the itinerary,",
        "  trip logistics, packing advice, or general destination knowledge.",
        "",
        "## Modifying the itinerary — you CAN do this, use the tools",
        "- You have the ability to propose itinerary changes. When the user asks, ALWAYS call",
        "  the appropriate tool — never say you cannot modify the itinerary.",
        "- To ADD a new item (e.g. 'add a museum', 'include X', 'put Y on day 2', 'can you",
        "  add Z'), call ProposeAddItem with: day (number), title, description, reason.",
        "- To REPLACE or SWAP an existing item, call ProposeItineraryChange with: day number,",
        "  item_index (0-based, first item = 0), replacement_title, replacement_description,"
        " reason.",
        "- After calling either tool, confirm to the user: 'I've proposed adding/replacing X —",
        "  check the approval banner above the itinerary to confirm.'",
        "- NEVER tell the user to click a Replace button or modify the UI themselves.",
        "- Only call these tools when the user explicitly requests a change to the itinerary.",
        "",
    ]

    # Trip overview
    if trip is not None:
        duration = (trip.end_date - trip.start_date).days + 1
        budget_str = (
            f"{trip.budget_total} {trip.budget_currency}" if trip.budget_total else "not set"
        )
        dest = trip.destination_city
        if trip.destination_country:
            dest += f", {trip.destination_country}"
        lines += [
            "## Current trip",
            f"Destination: {dest}",
            f"Dates: {trip.start_date} to {trip.end_date} ({duration} day{'s' if duration != 1 else ''})",  # noqa: E501
            f"Travelers: {trip.num_travelers}",
            f"Budget: {budget_str}",
        ]
        if trip.latitude and trip.longitude:
            lines.append(
                f"Destination coordinates: {trip.latitude:.4f}, {trip.longitude:.4f}"
                " (use as default search centre)"
            )
        lines.append("")
    else:
        lines += ["## Current trip", "Trip details not available.", ""]

    # Hotel
    if hotel is not None:
        lines.append("## Hotel")
        lines.append(f"Name: {hotel.name}")
        if hotel.star_rating:
            lines.append(f"Stars: {hotel.star_rating}")
        if hotel.address:
            lines.append(f"Address: {hotel.address}")
        if hotel.price_total:
            lines.append(f"Total price: {hotel.price_total} {hotel.price_currency or ''}")
        lines.append("")

    # Itinerary (titles + indices so LLM can reference them)
    if items:
        lines.append("## Itinerary (day: index. type — title)")
        by_day: dict[int, list[ItineraryItem]] = {}
        for item in items:
            by_day.setdefault(item.day_number, []).append(item)
        for day, day_items in sorted(by_day.items()):
            day_lines = [
                f"  {i}. {it.item_type} — {it.title}" for i, it in enumerate(day_items[:6])
            ]
            lines.append(f"Day {day}:")
            lines.extend(day_lines)
        lines.append("")

    # Traveler preferences (from DB)
    if pref is not None:
        parts: list[str] = []
        if pref.pace:
            parts.append(f"pace={pref.pace}")
        if pref.luxury_tier:
            parts.append(f"tier={pref.luxury_tier}")
        if pref.interests:
            parts.append(f"interests={', '.join(pref.interests)}")
        if pref.food_prefs:
            parts.append(f"food={', '.join(pref.food_prefs)}")
        if pref.walking_tolerance:
            parts.append(f"walking={pref.walking_tolerance}")
        if pref.budget_behavior:
            parts.append(f"budget_behavior={pref.budget_behavior}")
        if parts:
            lines += ["## Traveler preferences", ", ".join(parts), ""]

    # Past trips from Qdrant (for personalisation)
    past_trips = memory.get("past_trips") or []
    if past_trips:
        lines.append("## Past trips (for personalisation)")
        for pt in past_trips[:3]:
            city = pt.get("destination_city", "")
            country = pt.get("destination_country", "")
            loc = f"{city}, {country}" if country else city
            lines.append(f"- {loc}")
        lines.append("")

    lines += [
        "## How to use tools",
        "When searching, default to the destination coordinates listed above.",
        "After receiving tool results, give a specific answer that names real places from the results.",  # noqa: E501
        "If you want to narrow results (e.g. 'near the hotel'), adjust lat/lng accordingly if known.",  # noqa: E501
    ]

    return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_text(response: object) -> str:
    """Extract the text string from an AIMessage, handling list content blocks."""
    content = getattr(response, "content", "")
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    return str(content).strip()
