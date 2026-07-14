from typing import Annotated, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class TravelOSState(TypedDict):
    """
    Single source of truth passed between all agents in the graph.
    Never use module-level globals — always read/write through this state.
    """

    # Core identifiers
    trip_id: str
    user_id: str

    # Traveler data
    traveler_profiles: list[dict]

    # Itinerary: list of dicts matching ItineraryItem schema
    itinerary: list[dict]

    # Sub-states populated by their respective agents
    weather_state: dict  # keys: risk_flags, last_checked
    budget_state: dict  # keys: total, spent, by_category, breach_pct
    hotel_state: dict  # keys: candidates, selected
    events_state: dict  # keys: fetched, filtered, proposed, conflict_warnings
    packing_state: dict  # keys: categories, status

    # Semantic memory context injected by Travel Style agent
    memory_context: dict  # keys: preferences, travel_style_profile, past_trips

    # Pending approval records (dicts matching Approval schema)
    approval_queue: list[dict]

    # LangChain message history — accumulated across all agents
    agent_messages: Annotated[list[BaseMessage], add_messages]

    # Routing signal written by supervisor / each node
    current_step: str

    # Set on recoverable errors; supervisor reads this to decide retry vs fail
    error_state: dict | None

    # LangGraph checkpoint reference written after each completed run
    # Named run_checkpoint_ref to avoid collision with LangGraph's reserved "checkpoint_id" channel
    run_checkpoint_ref: str | None

    # Incremented by conflict_detection; caps at 3 to prevent infinite loops
    replan_iterations: int

    # Why the last replan was triggered — conflict_detection writes it, the
    # itinerary planner injects it into the regeneration prompt, then clears it.
    # NotRequired: absent on states built before this key existed.
    replan_feedback: NotRequired[list[str]]
