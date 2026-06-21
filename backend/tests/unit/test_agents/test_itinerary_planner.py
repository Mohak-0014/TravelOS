from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, SystemMessage

from backend.agents.itinerary_planner import (
    _MUST_SEE_MIN_SITELINKS,
    _build_prompt,
    _build_weather_state,
    _cluster_attractions,
    _compass_direction,
    _default_itinerary,
    _enforce_must_see,
    _item_to_dict,
    _ItemDraft,
    _parse_items,
    _parse_time,
    run,
)
from backend.graphs.state import TravelOSState
from backend.tools.places import Attraction
from backend.tools.weather import WeatherDay

# ── fixtures ──────────────────────────────────────────────────────────────────


def _mock_trip(
    trip_id: str = "trip-ip",
    destination_city: str = "Paris",
    destination_country: str | None = "FR",
    start_date: date = date(2026, 7, 1),
    end_date: date = date(2026, 7, 3),
    num_travelers: int = 2,
    budget_total: float | None = 3000.0,
    budget_currency: str = "EUR",
    latitude: float | None = 48.8566,
    longitude: float | None = 2.3522,
) -> MagicMock:
    trip = MagicMock()
    trip.id = trip_id
    trip.destination_city = destination_city
    trip.destination_country = destination_country
    trip.start_date = start_date
    trip.end_date = end_date
    trip.num_travelers = num_travelers
    trip.budget_total = budget_total
    trip.budget_currency = budget_currency
    trip.latitude = latitude
    trip.longitude = longitude
    return trip


def _mock_weather(d: date, is_adverse: bool = False) -> WeatherDay:
    return WeatherDay(
        date=d,
        temp_min_c=15.0,
        temp_max_c=25.0,
        precipitation_mm=0.0 if not is_adverse else 20.0,
        precipitation_prob=10 if not is_adverse else 85,
        condition_code=0 if not is_adverse else 63,
        condition_label="Clear sky" if not is_adverse else "Moderate rain",
        is_adverse=is_adverse,
    )


def _mock_attraction(name: str = "Louvre Museum", kinds: str = "museum") -> Attraction:
    return Attraction(
        osm_id="way/12345",
        name=name,
        lat=48.8606,
        lng=2.3376,
        kinds=kinds,
        source_ref="way/12345",
    )


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-ip",
        "user_id": "user-ip",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {
            "total": 3000.0,
            "spent": 0.0,
            "by_category": {},
            "breach_pct": 0.0,
            "currency": "EUR",
        },
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {
            "preferences": {},
            "travel_style_profile": {
                "travel_style_summary": "A culturally curious couple.",
                "style_tags": ["culture", "food", "moderate_pace"],
                "accommodation_preference": "Mid-range boutique hotels",
                "activity_preference": "Museums and local markets",
                "dining_preference": "Local cuisine",
                "daily_rhythm": "2-3 activities per day",
                "budget_priority": "Balanced spending",
            },
            "embedding_hits": [],
            "past_trips": [],
        },
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "itinerary_planner",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _llm_json(items: list[dict]) -> MagicMock:  # type: ignore[type-arg]
    import json

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=json.dumps(items)))
    return llm


def _valid_item_json(
    day: int = 1,
    item_date: str = "2026-07-01",
    item_type: str = "activity",
) -> dict:  # type: ignore[type-arg]
    return {
        "day_number": day,
        "item_date": item_date,
        "start_time": "09:00",
        "end_time": "12:00",
        "item_type": item_type,
        "title": "Visit the Louvre",
        "description": "Famous art museum.",
        "latitude": 48.8606,
        "longitude": 2.3376,
        "address": "Rue de Rivoli, Paris",
        "source_provider": "overpass",
        "source_ref": "way/12345",
        "est_cost": 20.0,
        "est_cost_currency": "EUR",
        "is_outdoor": False,
        "sort_order": 0,
    }


# ── run() — happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_returns_itinerary_in_state() -> None:
    trip = _mock_trip()
    items_json = [
        _valid_item_json(day=1, item_date="2026-07-01"),
        _valid_item_json(day=2, item_date="2026-07-02"),
        _valid_item_json(day=3, item_date="2026-07-03"),
    ]
    with (
        patch("backend.agents.itinerary_planner._load_trip", new=AsyncMock(return_value=trip)),
        patch(
            "backend.agents.itinerary_planner._resolve_coords",
            new=AsyncMock(return_value=(48.8566, 2.3522)),
        ),
        patch("backend.agents.itinerary_planner.fetch_weather", new=AsyncMock(return_value=[])),
        patch(
            "backend.agents.itinerary_planner.search_attractions", new=AsyncMock(return_value=[])
        ),
        patch("backend.agents.itinerary_planner._build_llm", return_value=_llm_json(items_json)),
        patch("backend.agents.itinerary_planner._persist_itinerary_items", new=AsyncMock()),
    ):
        result = await run(_base_state())

    assert "itinerary" in result
    assert len(result["itinerary"]) == 3


@pytest.mark.asyncio
async def test_run_returns_weather_state() -> None:
    trip = _mock_trip()
    weather = [
        _mock_weather(date(2026, 7, 1), is_adverse=False),
        _mock_weather(date(2026, 7, 2), is_adverse=True),
        _mock_weather(date(2026, 7, 3), is_adverse=False),
    ]
    with (
        patch("backend.agents.itinerary_planner._load_trip", new=AsyncMock(return_value=trip)),
        patch(
            "backend.agents.itinerary_planner._resolve_coords",
            new=AsyncMock(return_value=(48.85, 2.35)),
        ),
        patch(
            "backend.agents.itinerary_planner.fetch_weather", new=AsyncMock(return_value=weather)
        ),
        patch(
            "backend.agents.itinerary_planner.search_attractions", new=AsyncMock(return_value=[])
        ),
        patch(
            "backend.agents.itinerary_planner._build_llm",
            return_value=_llm_json([_valid_item_json()]),
        ),
        patch("backend.agents.itinerary_planner._persist_itinerary_items", new=AsyncMock()),
    ):
        result = await run(_base_state())

    ws = result["weather_state"]
    assert "risk_flags" in ws
    assert "2026-07-02" in ws["risk_flags"]
    assert "last_checked" in ws
    assert len(ws["forecast"]) == 3


@pytest.mark.asyncio
async def test_run_adds_system_message() -> None:
    trip = _mock_trip()
    with (
        patch("backend.agents.itinerary_planner._load_trip", new=AsyncMock(return_value=trip)),
        patch(
            "backend.agents.itinerary_planner._resolve_coords",
            new=AsyncMock(return_value=(48.85, 2.35)),
        ),
        patch("backend.agents.itinerary_planner.fetch_weather", new=AsyncMock(return_value=[])),
        patch(
            "backend.agents.itinerary_planner.search_attractions", new=AsyncMock(return_value=[])
        ),
        patch(
            "backend.agents.itinerary_planner._build_llm",
            return_value=_llm_json([_valid_item_json()]),
        ),
        patch("backend.agents.itinerary_planner._persist_itinerary_items", new=AsyncMock()),
    ):
        result = await run(_base_state())

    assert isinstance(result["agent_messages"][0], SystemMessage)
    assert "trip-ip" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_persists_items_to_db() -> None:
    trip = _mock_trip()
    persist_mock = AsyncMock()
    with (
        patch("backend.agents.itinerary_planner._load_trip", new=AsyncMock(return_value=trip)),
        patch(
            "backend.agents.itinerary_planner._resolve_coords",
            new=AsyncMock(return_value=(48.85, 2.35)),
        ),
        patch("backend.agents.itinerary_planner.fetch_weather", new=AsyncMock(return_value=[])),
        patch(
            "backend.agents.itinerary_planner.search_attractions", new=AsyncMock(return_value=[])
        ),
        patch(
            "backend.agents.itinerary_planner._build_llm",
            return_value=_llm_json([_valid_item_json()]),
        ),
        patch("backend.agents.itinerary_planner._persist_itinerary_items", new=persist_mock),
    ):
        await run(_base_state())

    persist_mock.assert_awaited_once()
    call_args = persist_mock.call_args
    assert call_args[0][0] == "trip-ip"  # trip_id
    assert len(call_args[0][2]) == 1  # items list


# ── run() — error & degradation paths ────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_returns_error_state_when_trip_not_found() -> None:
    with patch("backend.agents.itinerary_planner._load_trip", new=AsyncMock(return_value=None)):
        result = await run(_base_state())

    assert result["error_state"]["node"] == "itinerary_planner"


@pytest.mark.asyncio
async def test_run_uses_default_itinerary_when_llm_fails() -> None:
    trip = _mock_trip()
    failing_llm = MagicMock()
    failing_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
    with (
        patch("backend.agents.itinerary_planner._load_trip", new=AsyncMock(return_value=trip)),
        patch(
            "backend.agents.itinerary_planner._resolve_coords",
            new=AsyncMock(return_value=(48.85, 2.35)),
        ),
        patch("backend.agents.itinerary_planner.fetch_weather", new=AsyncMock(return_value=[])),
        patch(
            "backend.agents.itinerary_planner.search_attractions", new=AsyncMock(return_value=[])
        ),
        patch("backend.agents.itinerary_planner._build_llm", return_value=failing_llm),
        patch("backend.agents.itinerary_planner._persist_itinerary_items", new=AsyncMock()),
    ):
        result = await run(_base_state())

    # Default itinerary: one free item per day
    assert len(result["itinerary"]) == 3
    assert all(it["item_type"] == "free" for it in result["itinerary"])


@pytest.mark.asyncio
async def test_run_proceeds_without_coords() -> None:
    trip = _mock_trip(latitude=None, longitude=None)
    with (
        patch("backend.agents.itinerary_planner._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.itinerary_planner._resolve_coords", new=AsyncMock(return_value=None)),
        patch(
            "backend.agents.itinerary_planner._build_llm",
            return_value=_llm_json([_valid_item_json()]),
        ),
        patch("backend.agents.itinerary_planner._persist_itinerary_items", new=AsyncMock()),
    ):
        result = await run(_base_state())

    # Should still return weather_state (empty forecast)
    assert result["weather_state"]["risk_flags"] == []


# ── _parse_items ──────────────────────────────────────────────────────────────


def test_parse_items_valid_json() -> None:
    import json

    trip = _mock_trip()
    items = _parse_items(json.dumps([_valid_item_json()]), trip)
    assert len(items) == 1
    assert items[0].title == "Visit the Louvre"


def test_parse_items_rejects_out_of_range_dates() -> None:
    trip = _mock_trip(start_date=date(2026, 7, 1), end_date=date(2026, 7, 3))
    import json

    bad_item = _valid_item_json(item_date="2026-08-15")  # outside trip window
    items = _parse_items(json.dumps([bad_item]), trip)
    assert items == []


def test_parse_items_fixes_invalid_item_type() -> None:
    import json

    raw_item = _valid_item_json()
    raw_item["item_type"] = "sightseeing"  # not valid
    trip = _mock_trip()
    items = _parse_items(json.dumps([raw_item]), trip)
    assert len(items) == 1
    assert items[0].item_type == "activity"


def test_parse_items_reassigns_sort_order_sequentially() -> None:
    import json

    items_json = [
        {**_valid_item_json(day=1, item_date="2026-07-01"), "sort_order": 99},
        {**_valid_item_json(day=1, item_date="2026-07-01"), "title": "Lunch", "sort_order": 50},
    ]
    trip = _mock_trip()
    items = _parse_items(json.dumps(items_json), trip)
    assert items[0].sort_order == 0
    assert items[1].sort_order == 1


def test_parse_items_returns_empty_on_invalid_json() -> None:
    trip = _mock_trip()
    assert _parse_items("not json at all", trip) == []
    assert _parse_items("{}", trip) == []  # dict not array


def test_parse_items_json_wrapped_in_prose() -> None:
    import json

    wrapped = f"Here is your itinerary:\n{json.dumps([_valid_item_json()])}\nEnjoy!"
    trip = _mock_trip()
    items = _parse_items(wrapped, trip)
    assert len(items) == 1


# ── _default_itinerary ────────────────────────────────────────────────────────


def test_default_itinerary_has_one_item_per_day() -> None:
    trip = _mock_trip(start_date=date(2026, 7, 1), end_date=date(2026, 7, 5))
    items = _default_itinerary(trip)
    assert len(items) == 5


def test_default_itinerary_item_types_are_free() -> None:
    trip = _mock_trip()
    items = _default_itinerary(trip)
    assert all(it.item_type == "free" for it in items)


def test_default_itinerary_dates_are_sequential() -> None:
    trip = _mock_trip(start_date=date(2026, 7, 1), end_date=date(2026, 7, 3))
    items = _default_itinerary(trip)
    assert items[0].item_date == "2026-07-01"
    assert items[1].item_date == "2026-07-02"
    assert items[2].item_date == "2026-07-03"


def test_default_itinerary_day_numbers_start_at_one() -> None:
    trip = _mock_trip()
    items = _default_itinerary(trip)
    assert items[0].day_number == 1


# ── _build_weather_state ──────────────────────────────────────────────────────


def test_build_weather_state_flags_adverse_days() -> None:
    weather = [
        _mock_weather(date(2026, 7, 1), is_adverse=False),
        _mock_weather(date(2026, 7, 2), is_adverse=True),
    ]
    ws = _build_weather_state(weather)
    assert "2026-07-02" in ws["risk_flags"]
    assert "2026-07-01" not in ws["risk_flags"]


def test_build_weather_state_empty_input() -> None:
    ws = _build_weather_state([])
    assert ws["risk_flags"] == []
    assert ws["forecast"] == []
    assert "last_checked" in ws


def test_build_weather_state_forecast_has_correct_shape() -> None:
    weather = [_mock_weather(date(2026, 7, 1))]
    ws = _build_weather_state(weather)
    assert ws["forecast"][0]["date"] == "2026-07-01"
    assert "condition" in ws["forecast"][0]
    assert "is_adverse" in ws["forecast"][0]


# ── _parse_time ───────────────────────────────────────────────────────────────


def test_parse_time_valid() -> None:
    from datetime import time

    assert _parse_time("09:30") == time(9, 30)
    assert _parse_time("14:00") == time(14, 0)


def test_parse_time_none_returns_none() -> None:
    assert _parse_time(None) is None


def test_parse_time_invalid_returns_none() -> None:
    assert _parse_time("not-a-time") is None
    assert _parse_time("25:00") is None


# ── _build_prompt ─────────────────────────────────────────────────────────────


def test_build_prompt_includes_destination() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {})
    assert "Paris" in prompt
    assert "FR" in prompt


def test_build_prompt_includes_style_tags_when_present() -> None:
    trip = _mock_trip()
    style = {
        "style_tags": ["culture", "food"],
        "travel_style_summary": "x",
        "accommodation_preference": "x",
        "activity_preference": "x",
        "dining_preference": "x",
        "daily_rhythm": "x",
        "budget_priority": "x",
    }
    prompt = _build_prompt(trip, style, [], [], [], {})
    assert "culture" in prompt
    assert "food" in prompt


def test_build_prompt_flags_adverse_weather() -> None:
    trip = _mock_trip()
    weather = [_mock_weather(date(2026, 7, 1), is_adverse=True)]
    prompt = _build_prompt(trip, {}, weather, [], [], {})
    assert "ADVERSE" in prompt


def test_build_prompt_includes_attraction_names() -> None:
    trip = _mock_trip()
    attractions = [_mock_attraction("Eiffel Tower", "attraction")]
    prompt = _build_prompt(trip, {}, [], attractions, [], {})
    assert "Eiffel Tower" in prompt


def test_build_prompt_note_when_no_attractions() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {})
    assert "No attraction data available" in prompt


# ── _item_to_dict ─────────────────────────────────────────────────────────────


def test_item_to_dict_roundtrips() -> None:
    item = _ItemDraft(
        day_number=1,
        item_date="2026-07-01",
        item_type="activity",
        title="Test",
        sort_order=0,
    )
    d = _item_to_dict(item)
    assert d["day_number"] == 1
    assert d["title"] == "Test"
    assert d["item_type"] == "activity"


# ── _cluster_attractions ──────────────────────────────────────────────────────


def _make_attraction(
    name: str, lat: float, lng: float, kinds: str = "museum", is_major: bool = False
) -> Attraction:
    osm_id = f"node/{hash(name) & 0xFFFF}"
    return Attraction(
        osm_id=osm_id,
        name=name,
        lat=lat,
        lng=lng,
        kinds=kinds,
        source_ref=osm_id,
        is_major=is_major,
    )


def test_cluster_attractions_empty_returns_empty() -> None:
    assert _cluster_attractions([]) == []


def test_cluster_attractions_single_attraction_is_group_a() -> None:
    clusters = _cluster_attractions([_make_attraction("Louvre", 48.860, 2.337)])
    assert len(clusters) == 1
    label, anchor, members = clusters[0]
    assert label == "A"
    assert anchor == "Louvre"
    assert len(members) == 1


def test_cluster_attractions_nearby_items_share_group() -> None:
    # Both within the same ~1 km cell (cell 5428, 211)
    a1 = _make_attraction("A", lat=48.853, lng=2.322)
    a2 = _make_attraction("B", lat=48.858, lng=2.328)
    clusters = _cluster_attractions([a1, a2])
    assert len(clusters) == 1
    assert len(clusters[0][2]) == 2


def test_cluster_attractions_distant_items_in_separate_groups() -> None:
    a1 = _make_attraction("Near", lat=48.853, lng=2.322)
    a2 = _make_attraction("Far", lat=48.910, lng=2.390)
    clusters = _cluster_attractions([a1, a2])
    assert len(clusters) == 2


def test_cluster_attractions_largest_group_is_labeled_a() -> None:
    # 3 attractions in the same cell, 1 far away
    close = [_make_attraction(f"C{i}", lat=48.853 + i * 0.001, lng=2.322) for i in range(3)]
    far = [_make_attraction("Far", lat=48.910, lng=2.390)]
    clusters = _cluster_attractions(close + far)
    assert clusters[0][0] == "A"
    assert len(clusters[0][2]) == 3


def test_cluster_attractions_labels_are_sequential() -> None:
    # Two separate cells → labels A and B
    a1 = _make_attraction("Near", lat=48.853, lng=2.322)
    a2 = _make_attraction("Far", lat=48.910, lng=2.390)
    clusters = _cluster_attractions([a1, a2])
    labels = [c[0] for c in clusters]
    assert "A" in labels
    assert "B" in labels


# ── _compass_direction ────────────────────────────────────────────────────────


def test_compass_north() -> None:
    assert _compass_direction(0.0, 0.0, 0.01, 0.0) == "north"


def test_compass_south() -> None:
    assert _compass_direction(0.0, 0.0, -0.01, 0.0) == "south"


def test_compass_east() -> None:
    assert _compass_direction(0.0, 0.0, 0.0, 0.01) == "east"


def test_compass_west() -> None:
    assert _compass_direction(0.0, 0.0, 0.0, -0.01) == "west"


def test_compass_northeast() -> None:
    assert _compass_direction(0.0, 0.0, 0.01, 0.01) == "northeast"


def test_compass_southwest() -> None:
    assert _compass_direction(0.0, 0.0, -0.01, -0.01) == "southwest"


def test_compass_central_when_same_point() -> None:
    assert _compass_direction(1.0, 1.0, 1.0, 1.0) == "central"


# ── _build_prompt — clustering and scheduling sections ────────────────────────


def test_build_prompt_shows_group_labels_for_attractions() -> None:
    trip = _mock_trip()
    attractions = [_mock_attraction("Eiffel Tower", "attraction")]
    prompt = _build_prompt(trip, {}, [], attractions, [], {})
    assert "Group A" in prompt
    assert "Eiffel Tower" in prompt


def test_build_prompt_shows_opening_hours_when_present() -> None:
    trip = _mock_trip()
    a = Attraction(
        osm_id="way/1",
        name="Opera House",
        lat=48.872,
        lng=2.331,
        kinds="attraction",
        source_ref="way/1",
        opening_hours="Mo-Sa 10:00-22:00",
    )
    prompt = _build_prompt(trip, {}, [], [a], [], {})
    assert "Mo-Sa 10:00-22:00" in prompt


def test_build_prompt_omits_hours_when_none() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [_mock_attraction()], [], {})
    assert "hours=" not in prompt


def test_build_prompt_includes_walking_constraint_low() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {}, walking_tolerance="low")
    assert "500" in prompt


def test_build_prompt_includes_walking_constraint_high() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {}, walking_tolerance="high")
    assert "5000" in prompt


def test_build_prompt_defaults_to_medium_walking_tolerance() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {})
    assert "2000" in prompt


def test_build_prompt_includes_scheduling_guidelines() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {})
    assert "Scheduling Guidelines" in prompt
    assert "12:00" in prompt  # lunch hint from _MEAL_RULES
    assert "19:00" in prompt  # dinner hint
    assert "09:00" in prompt  # museum window


# ── _build_prompt — prominence + variety (task #23) ───────────────────────────


def test_build_prompt_marks_major_attractions_with_star() -> None:
    trip = _mock_trip()
    major = _make_attraction("Eiffel Tower", 48.8584, 2.2945, "attraction", is_major=True)
    prompt = _build_prompt(trip, {}, [], [major], [], {})
    assert "★" in prompt
    assert "Eiffel Tower" in prompt


def test_build_prompt_has_no_star_when_no_major_attractions() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [_mock_attraction()], [], {})
    assert "★" not in prompt


def test_build_prompt_ranks_major_attractions_first() -> None:
    trip = _mock_trip()
    # All three share one cluster; the anchor is a third (minor) venue so the two
    # compared names appear only in the ranked member list.
    anchor = _make_attraction("MMM Anchor Place", 48.8606, 2.3376, "attraction")
    minor = _make_attraction("AAA Minor Gallery", 48.8606, 2.3376, "gallery")
    major = _make_attraction("ZZZ Major Museum", 48.8606, 2.3376, "museum", is_major=True)
    prompt = _build_prompt(trip, {}, [], [anchor, minor, major], [], {})
    assert prompt.index("ZZZ Major Museum") < prompt.index("AAA Minor Gallery")


def test_build_prompt_includes_prominence_and_variety_rules() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {})
    assert "Selection priorities" in prompt
    assert "Prominence" in prompt
    assert "2 venues of the same kind" in prompt  # same-type cap


def test_build_prompt_includes_example_day() -> None:
    trip = _mock_trip()
    prompt = _build_prompt(trip, {}, [], [], [], {})
    assert "well-balanced day" in prompt


def test_build_prompt_lists_must_see_landmarks() -> None:
    trip = _mock_trip()
    famous = _make_attraction("World Famous Fort", 48.86, 2.34, "attraction", is_major=True)
    famous.prominence = 95
    obscure = _make_attraction("Tiny Tomb", 48.861, 2.341, "monument", is_major=True)
    obscure.prominence = 2
    prompt = _build_prompt(trip, {}, [], [famous, obscure], [], {})
    assert "MUST-SEE landmarks" in prompt
    assert "World Famous Fort" in prompt
    # First mention of the famous sight is in the MUST-SEE block (before the cluster list).
    assert prompt.index("MUST-SEE") < prompt.index("World Famous Fort")


def test_build_prompt_no_must_see_when_nothing_famous() -> None:
    trip = _mock_trip()
    a = _make_attraction("Local Spot", 48.86, 2.34, "attraction", is_major=True)  # prominence 0
    prompt = _build_prompt(trip, {}, [], [a], [], {})
    assert "MUST-SEE landmarks" not in prompt


# ── _enforce_must_see ─────────────────────────────────────────────────────────


def _famous(name: str, ref: str = "") -> Attraction:
    """Return a famous (must-see) attraction with sitelink count above the threshold."""
    a = _make_attraction(name, 48.86, 2.34, "attraction", is_major=True)
    a.prominence = _MUST_SEE_MIN_SITELINKS + 5
    a.source_ref = ref or a.osm_id
    return a


def _item(title: str, day: int = 1, ref: str = "", lat: float | None = None) -> _ItemDraft:
    return _ItemDraft(
        day_number=day,
        item_date=f"2026-07-0{day}",
        item_type="activity",
        title=title,
        latitude=lat,
        longitude=2.34 if lat is not None else None,
        source_ref=ref or None,
        sort_order=0,
    )


def test_enforce_must_see_noop_when_no_must_sees() -> None:
    trip = _mock_trip()
    obscure = _make_attraction("Tiny Tomb", 48.86, 2.34)  # prominence 0 → not must-see
    items = [_item("Random Walk")]
    assert _enforce_must_see(items, [obscure], trip) == items


def test_enforce_must_see_noop_when_all_already_scheduled() -> None:
    trip = _mock_trip()
    eiffel = _famous("Eiffel Tower", ref="way/5013364")
    items = [_item("Eiffel Tower", ref="way/5013364")]
    result = _enforce_must_see(items, [eiffel], trip)
    assert result == items


def test_enforce_must_see_swaps_missing_icon_into_slot() -> None:
    trip = _mock_trip(end_date=date(2026, 7, 3))  # 3 days → max_swaps = activity_count - 6
    eiffel = _famous("Eiffel Tower", ref="way/eiffel")

    # 3 days × 3 activity slots each = 9 activity items; max_swaps = 9 - 6 = 3
    items = [
        _item("Filler A", day=1),
        _item("Filler B", day=2),
        _item("Filler C", day=3),
        _item("Filler D", day=1),
        _item("Filler E", day=2),
        _item("Filler F", day=3),
        _item("Filler G", day=1),
        _item("Filler H", day=2),
        _item("Filler I", day=3),
    ]
    result = _enforce_must_see(items, [eiffel], trip)
    titles = [i.title for i in result]
    assert "Eiffel Tower" in titles


def test_enforce_must_see_preserves_day_and_sort_order() -> None:
    trip = _mock_trip(end_date=date(2026, 7, 3))
    louvre = _famous("Louvre Museum", ref="way/louvre")

    # 8 items with real coords (won't be replaced first); 1 LLM-invented on day 2 with metadata
    real = [_item(f"Real{i}", day=d, lat=48.86) for i, d in enumerate([1, 1, 1, 2, 2, 3, 3, 3])]
    target = _ItemDraft(
        day_number=2,
        item_date="2026-07-02",
        item_type="activity",
        title="LLM Filler",
        start_time="10:00",
        sort_order=5,
    )
    items = real + [target]  # 9 items: max_swaps = 9 - 6 = 3; target has no coords → replaced first
    result = _enforce_must_see(items, [louvre], trip)

    enforced = next(i for i in result if i.title == "Louvre Museum")
    assert enforced.day_number == 2
    assert enforced.sort_order == 5
    assert enforced.start_time == "10:00"


def test_enforce_must_see_respects_max_swaps_cap() -> None:
    trip = _mock_trip(end_date=date(2026, 7, 1))  # 1 day
    # 2 activity items, trip_days=1 → max_swaps = 2 - 2 = 0 → no swaps
    icon_a = _famous("Icon A", ref="way/a")
    icon_b = _famous("Icon B", ref="way/b")
    items = [_item("Slot 1"), _item("Slot 2")]
    result = _enforce_must_see(items, [icon_a, icon_b], trip)
    titles = [i.title for i in result]
    assert "Icon A" not in titles
    assert "Icon B" not in titles


def test_enforce_must_see_prefers_invented_slots_over_real_ones() -> None:
    trip = _mock_trip(end_date=date(2026, 7, 2))  # 2 days
    icon = _famous("Icon", ref="way/icon")

    # 6 items across 2 days: max_swaps = 6 - 4 = 2
    real_slot = _item("Real Place", day=1, ref="way/real", lat=48.86)  # has coords → lower priority
    invented = _item("LLM Filler", day=1)  # no coords → replaced first
    items = [
        real_slot,
        invented,
        _item("X2", day=2),
        _item("X3", day=2),
        _item("X4", day=1),
        _item("X5", day=2),
    ]
    result = _enforce_must_see(items, [icon], trip)

    # The invented slot (no lat/lng) should have been replaced, not the real one
    titles = [i.title for i in result]
    assert "LLM Filler" not in titles
    assert "Real Place" in titles
    assert "Icon" in titles
