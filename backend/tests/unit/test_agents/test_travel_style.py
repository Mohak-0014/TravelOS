from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, SystemMessage

from backend.agents.travel_style import (
    _default_profile,
    _parse_profile,
    _preference_to_dict,
    _trip_to_context,
    run,
)
from backend.graphs.state import TravelOSState

# ── helpers ───────────────────────────────────────────────────────────────────


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-ts",
        "user_id": "user-ts",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {"risk_flags": [], "last_checked": None},
        "budget_state": {"total": None, "spent": 0.0, "by_category": {}, "breach_pct": 0.0},
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "travel_style",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _mock_trip(
    destination_city: str = "Paris",
    destination_country: str | None = "FR",
    start_date: date = date(2026, 7, 1),
    end_date: date = date(2026, 7, 7),
    num_travelers: int = 2,
    budget_total: float | None = 3000.0,
    budget_currency: str = "USD",
) -> MagicMock:
    trip = MagicMock()
    trip.destination_city = destination_city
    trip.destination_country = destination_country
    trip.start_date = start_date
    trip.end_date = end_date
    trip.num_travelers = num_travelers
    trip.budget_total = budget_total
    trip.budget_currency = budget_currency
    return trip


def _mock_pref(
    pace: str = "moderate",
    luxury_tier: str = "mid",
    walking_tolerance: str = "high",
    food_prefs: list | None = None,
    interests: list | None = None,
    budget_behavior: str = "balanced",
) -> MagicMock:
    pref = MagicMock()
    pref.pace = pace
    pref.luxury_tier = luxury_tier
    pref.walking_tolerance = walking_tolerance
    pref.food_prefs = food_prefs or ["local", "vegetarian"]
    pref.interests = interests or ["culture", "history"]
    pref.budget_behavior = budget_behavior
    return pref


_VALID_PROFILE_JSON = """{
  "travel_style_summary": "A culturally curious couple.",
  "style_tags": ["culture", "food", "moderate_pace"],
  "accommodation_preference": "Mid-range boutique hotels",
  "activity_preference": "Museums and local markets",
  "dining_preference": "Local cuisine",
  "daily_rhythm": "2-3 activities per day",
  "budget_priority": "Balanced spending"
}"""


def _mock_llm(content: str = _VALID_PROFILE_JSON) -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


# ── run() — happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_returns_memory_context() -> None:
    trip, pref = _mock_trip(), _mock_pref()
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, pref))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(_base_state())

    assert "memory_context" in result
    mc = result["memory_context"]
    assert "preferences" in mc
    assert "travel_style_profile" in mc
    assert mc["embedding_hits"] == []
    assert mc["past_trips"] == []


@pytest.mark.asyncio
async def test_run_adds_system_message() -> None:
    trip, pref = _mock_trip(), _mock_pref()
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, pref))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(_base_state())

    msgs = result["agent_messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], SystemMessage)
    assert "trip-ts" in msgs[0].content


@pytest.mark.asyncio
async def test_run_profile_contains_expected_keys() -> None:
    trip, pref = _mock_trip(), _mock_pref()
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, pref))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(_base_state())

    profile = result["memory_context"]["travel_style_profile"]
    for key in (
        "travel_style_summary",
        "style_tags",
        "accommodation_preference",
        "activity_preference",
        "dining_preference",
        "daily_rhythm",
        "budget_priority",
    ):
        assert key in profile, f"Missing key: {key}"


# ── budget_state backfill ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_backfills_budget_total_when_null() -> None:
    trip = _mock_trip(budget_total=4500.0, budget_currency="EUR")
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, None))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(
            _base_state(
                budget_state={"total": None, "spent": 0.0, "by_category": {}, "breach_pct": 0.0}
            )
        )

    assert "budget_state" in result
    assert result["budget_state"]["total"] == 4500.0
    assert result["budget_state"]["currency"] == "EUR"


@pytest.mark.asyncio
async def test_run_preserves_existing_budget_total() -> None:
    trip = _mock_trip(budget_total=9000.0)
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, None))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(
            _base_state(
                budget_state={"total": 5000.0, "spent": 0.0, "by_category": {}, "breach_pct": 0.0}
            )
        )

    assert "budget_state" not in result


@pytest.mark.asyncio
async def test_run_skips_budget_backfill_when_trip_missing() -> None:
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(None, None))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(_base_state())

    assert "budget_state" not in result


# ── graceful degradation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_uses_default_profile_when_llm_fails() -> None:
    trip, pref = _mock_trip(), _mock_pref()
    failing_llm = MagicMock()
    failing_llm.ainvoke = AsyncMock(side_effect=RuntimeError("API down"))

    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, pref))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=failing_llm),
    ):
        result = await run(_base_state())

    profile = result["memory_context"]["travel_style_profile"]
    assert "travel_style_summary" in profile
    assert "culture" in profile["style_tags"]


@pytest.mark.asyncio
async def test_run_uses_default_profile_when_llm_returns_invalid_json() -> None:
    trip, pref = _mock_trip(), _mock_pref()
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, pref))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm("not json")),
    ):
        result = await run(_base_state())

    profile = result["memory_context"]["travel_style_profile"]
    assert "travel_style_summary" in profile


@pytest.mark.asyncio
async def test_run_succeeds_with_no_preferences() -> None:
    trip = _mock_trip()
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(trip, None))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(_base_state())

    assert result["memory_context"]["preferences"] == {}


@pytest.mark.asyncio
async def test_run_succeeds_with_no_trip_and_no_pref() -> None:
    with (
        patch(
            "backend.agents.travel_style._load_db_context", new=AsyncMock(return_value=(None, None))
        ),
        patch("backend.agents.travel_style._build_llm", return_value=_mock_llm()),
    ):
        result = await run(_base_state())

    assert "memory_context" in result


# ── _preference_to_dict ───────────────────────────────────────────────────────


def test_preference_to_dict_with_full_pref() -> None:
    pref = _mock_pref()
    d = _preference_to_dict(pref)
    assert d["pace"] == "moderate"
    assert d["luxury_tier"] == "mid"
    assert d["walking_tolerance"] == "high"
    assert "local" in d["food_prefs"]
    assert "culture" in d["interests"]
    assert d["budget_behavior"] == "balanced"


def test_preference_to_dict_with_none() -> None:
    assert _preference_to_dict(None) == {}


def test_preference_to_dict_null_food_prefs_returns_empty_list() -> None:
    pref = _mock_pref()
    pref.food_prefs = None
    d = _preference_to_dict(pref)
    assert d["food_prefs"] == []


# ── _trip_to_context ──────────────────────────────────────────────────────────


def test_trip_to_context_includes_destination_and_dates() -> None:
    trip = _mock_trip()
    ctx = _trip_to_context(trip)
    assert "Paris" in ctx
    assert "FR" in ctx
    assert "2026-07-01" in ctx
    assert "7 days" in ctx


def test_trip_to_context_none_returns_fallback() -> None:
    ctx = _trip_to_context(None)
    assert "unknown" in ctx


def test_trip_to_context_omits_country_when_none() -> None:
    trip = _mock_trip(destination_country=None)
    ctx = _trip_to_context(trip)
    assert ", None" not in ctx


def test_trip_to_context_no_budget_shows_unspecified() -> None:
    trip = _mock_trip(budget_total=None)
    ctx = _trip_to_context(trip)
    assert "unspecified" in ctx


# ── _parse_profile ────────────────────────────────────────────────────────────


def test_parse_profile_valid_json() -> None:
    profile = _parse_profile(_VALID_PROFILE_JSON)
    assert profile["travel_style_summary"] == "A culturally curious couple."
    assert "culture" in profile["style_tags"]


def test_parse_profile_json_wrapped_in_prose() -> None:
    raw = f"Here is my analysis:\n{_VALID_PROFILE_JSON}\nHope this helps."
    profile = _parse_profile(raw)
    assert "travel_style_summary" in profile


def test_parse_profile_invalid_json_returns_default() -> None:
    profile = _parse_profile("This is not JSON at all")
    assert "travel_style_summary" in profile
    assert profile["style_tags"] == ["culture", "food", "moderate_pace"]


# ── _default_profile ──────────────────────────────────────────────────────────


def test_default_profile_has_all_required_keys() -> None:
    profile = _default_profile()
    for key in (
        "travel_style_summary",
        "style_tags",
        "accommodation_preference",
        "activity_preference",
        "dining_preference",
        "daily_rhythm",
        "budget_priority",
    ):
        assert key in profile


def test_default_profile_style_tags_is_list() -> None:
    profile = _default_profile()
    assert isinstance(profile["style_tags"], list)
    assert len(profile["style_tags"]) > 0
