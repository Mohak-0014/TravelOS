from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.weather import (
    _build_approval,
    _condition_for_date,
    _empty_weather_state,
    _item_to_dict,
    _next_alternative,
    create_approvals,
    impact_assessment,
    weather_adaptation,
    weather_check,
)
from backend.graphs.state import TravelOSState
from backend.tools.places import Attraction
from backend.tools.weather import WeatherDay

# ── fixtures ──────────────────────────────────────────────────────────────────


def _mock_trip(
    trip_id: str = "trip-w",
    city: str = "Rome",
    country: str = "IT",
    start: date = date(2026, 8, 1),
    end: date = date(2026, 8, 5),
    lat: float | None = 41.9,
    lng: float | None = 12.5,
) -> MagicMock:
    t = MagicMock()
    t.id = trip_id
    t.user_id = "user-1"
    t.destination_city = city
    t.destination_country = country
    t.start_date = start
    t.end_date = end
    t.latitude = lat
    t.longitude = lng
    return t


def _mock_weather_day(
    d: str = "2026-08-02",
    is_adverse: bool = True,
    condition: str = "Heavy rain",
) -> WeatherDay:
    return WeatherDay(
        date=date.fromisoformat(d),
        temp_min_c=15.0,
        temp_max_c=22.0,
        precipitation_mm=25.0,
        precipitation_prob=85,
        condition_code=65,
        condition_label=condition,
        is_adverse=is_adverse,
    )


def _base_state(trip_id: str = "trip-w") -> TravelOSState:
    return {  # type: ignore[return-value]
        "trip_id": trip_id,
        "user_id": "user-1",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {
            "risk_flags": [],
            "last_checked": None,
            "forecast": [],
            "affected_items": [],
        },
        "budget_state": {"total": None, "spent": 0.0, "by_category": {}, "breach_pct": 0.0},
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "start",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }


def _mock_item() -> MagicMock:
    item = MagicMock()
    item.id = "item-1"
    item.trip_id = "trip-w"
    item.day_number = 2
    item.item_date = date(2026, 8, 2)
    item.start_time = time(10, 0)
    item.end_time = time(12, 0)
    item.item_type = "activity"
    item.title = "Colosseum Tour"
    item.description = "Walking tour of the Colosseum."
    item.latitude = 41.89
    item.longitude = 12.49
    item.address = "Piazza del Colosseo"
    item.source_provider = "overpass"
    item.source_ref = "way/123"
    item.est_cost = 20.0
    item.est_cost_currency = "EUR"
    item.is_outdoor = True
    item.sort_order = 0
    return item


# ── _parse_alternative ────────────────────────────────────────────────────────


def _indoor_attraction(name: str = "Vatican Museum", ref: str = "way/vm") -> Attraction:
    return Attraction(
        osm_id=ref,
        name=name,
        lat=41.9,
        lng=12.45,
        kinds="museum",
        category="museum_gallery",
        source_ref=ref,
    )


def test_next_alternative_is_grounded_in_pool_venue() -> None:
    candidates = [_indoor_attraction()]
    alt = _next_alternative(candidates)
    assert alt is not None
    assert alt["title"] == "Vatican Museum"
    assert alt["is_outdoor"] is False
    assert alt["source_ref"] == "way/vm"  # grounding: real OSM ref, never invented
    assert alt["latitude"] == 41.9
    assert candidates == []  # consumed — no duplicate proposals


def test_next_alternative_empty_pool_returns_none() -> None:
    assert _next_alternative([]) is None


# ── _build_approval ───────────────────────────────────────────────────────────


def test_build_approval_structure() -> None:
    item = {
        "id": "item-1",
        "title": "Colosseum Tour",
        "item_date": "2026-08-02",
        "day_number": 2,
        "start_time": "10:00",
        "end_time": "12:00",
        "sort_order": 0,
    }
    alternative = {
        "title": "Vatican Museum",
        "description": "Indoors.",
        "item_type": "activity",
        "is_outdoor": False,
    }
    weather_state = {
        "forecast": [{"date": "2026-08-02", "condition": "Heavy rain", "is_adverse": True}]
    }
    approval = _build_approval("trip-w", item, alternative, weather_state)

    assert approval["trip_id"] == "trip-w"
    assert approval["change_type"] == "weather_replan"
    assert approval["proposed_by"] == "weather_agent"
    assert "Colosseum Tour" in approval["summary"]
    assert "Vatican Museum" in approval["summary"]
    assert approval["payload"]["original_item"] == item
    assert approval["payload"]["alternative_item"]["day_number"] == 2
    assert approval["payload"]["weather_condition"] == "Heavy rain"
    assert approval["status"] == "pending"
    assert "id" in approval


# ── _condition_for_date ───────────────────────────────────────────────────────


def test_condition_for_date_found() -> None:
    forecast = [{"date": "2026-08-02", "condition": "Thunderstorm"}]
    assert _condition_for_date("2026-08-02", forecast) == "Thunderstorm"


def test_condition_for_date_not_found() -> None:
    assert _condition_for_date("2026-08-03", []) == "Adverse weather"


# ── _empty_weather_state ──────────────────────────────────────────────────────


def test_empty_weather_state_keys() -> None:
    ws = _empty_weather_state()
    assert ws["risk_flags"] == []
    assert ws["forecast"] == []
    assert ws["affected_items"] == []
    assert ws["last_checked"] is not None


# ── _item_to_dict ─────────────────────────────────────────────────────────────


def test_item_to_dict() -> None:
    mock_item = _mock_item()
    d = _item_to_dict(mock_item)
    assert d["id"] == "item-1"
    assert d["item_date"] == "2026-08-02"
    assert d["start_time"] == "10:00"
    assert d["is_outdoor"] is True
    assert d["est_cost"] == 20.0


def test_item_to_dict_none_times() -> None:
    mock_item = _mock_item()
    mock_item.start_time = None
    mock_item.end_time = None
    mock_item.est_cost = None
    d = _item_to_dict(mock_item)
    assert d["start_time"] is None
    assert d["end_time"] is None
    assert d["est_cost"] is None


# ── weather_check ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_weather_check_with_adverse_days() -> None:
    state = _base_state()
    adverse_day = _mock_weather_day("2026-08-02", is_adverse=True)
    clear_day = _mock_weather_day("2026-08-03", is_adverse=False, condition="Clear sky")

    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_mock_trip())),
        patch("backend.agents.weather._resolve_coords", AsyncMock(return_value=(41.9, 12.5))),
        patch(
            "backend.agents.weather.fetch_weather", AsyncMock(return_value=[adverse_day, clear_day])
        ),
        patch("backend.agents.weather._save_weather_snapshots", AsyncMock()),
    ):
        result = await weather_check(state)

    assert result["weather_state"]["risk_flags"] == ["2026-08-02"]
    assert len(result["weather_state"]["forecast"]) == 2
    assert result["current_step"] == "impact_assessment"
    assert result["weather_state"]["last_checked"] is not None


@pytest.mark.asyncio
async def test_weather_check_no_adverse_days() -> None:
    state = _base_state()
    clear = _mock_weather_day("2026-08-01", is_adverse=False, condition="Clear sky")

    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_mock_trip())),
        patch("backend.agents.weather._resolve_coords", AsyncMock(return_value=(41.9, 12.5))),
        patch("backend.agents.weather.fetch_weather", AsyncMock(return_value=[clear])),
        patch("backend.agents.weather._save_weather_snapshots", AsyncMock()),
    ):
        result = await weather_check(state)

    assert result["weather_state"]["risk_flags"] == []


@pytest.mark.asyncio
async def test_weather_check_trip_not_found() -> None:
    state = _base_state()
    with patch("backend.agents.weather._load_trip", AsyncMock(return_value=None)):
        result = await weather_check(state)

    assert result["weather_state"]["risk_flags"] == []
    assert result["current_step"] == "impact_assessment"


@pytest.mark.asyncio
async def test_weather_check_no_coords() -> None:
    state = _base_state()
    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_mock_trip())),
        patch("backend.agents.weather._resolve_coords", AsyncMock(return_value=None)),
    ):
        result = await weather_check(state)

    assert result["weather_state"]["risk_flags"] == []


# ── impact_assessment ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_impact_assessment_with_affected_items() -> None:
    item_dict = _item_to_dict(_mock_item())
    state = _base_state()
    state["weather_state"] = {
        "risk_flags": ["2026-08-02"],
        "forecast": [],
        "last_checked": "now",
        "affected_items": [],
    }

    with patch("backend.agents.weather._load_affected_items", AsyncMock(return_value=[item_dict])):
        result = await impact_assessment(state)

    assert len(result["weather_state"]["affected_items"]) == 1
    assert result["weather_state"]["affected_items"][0]["title"] == "Colosseum Tour"
    assert result["current_step"] == "weather_adaptation"


@pytest.mark.asyncio
async def test_impact_assessment_no_risk_flags() -> None:
    state = _base_state()
    state["weather_state"] = {
        "risk_flags": [],
        "forecast": [],
        "last_checked": "now",
        "affected_items": [],
    }

    result = await impact_assessment(state)

    assert result["weather_state"]["affected_items"] == []
    assert result["current_step"] == "weather_adaptation"


# ── weather_adaptation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_weather_adaptation_proposes_alternatives() -> None:
    item_dict = _item_to_dict(_mock_item())
    state = _base_state()
    state["weather_state"] = {
        "risk_flags": ["2026-08-02"],
        "forecast": [{"date": "2026-08-02", "condition": "Heavy rain", "is_adverse": True}],
        "last_checked": "now",
        "affected_items": [item_dict],
    }

    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_mock_trip())),
        patch(
            "backend.agents.weather._indoor_candidates",
            AsyncMock(return_value=[_indoor_attraction()]),
        ),
    ):
        result = await weather_adaptation(state)

    assert len(result["approval_queue"]) == 1
    approval = result["approval_queue"][0]
    assert approval["change_type"] == "weather_replan"
    # Grounded replacement: carries the real venue's coordinates and OSM ref
    alt = approval["payload"]["alternative_item"]
    assert alt["source_ref"] == "way/vm"
    assert alt["latitude"] == 41.9
    assert result["current_step"] == "create_approvals"


@pytest.mark.asyncio
async def test_weather_adaptation_no_affected_items() -> None:
    state = _base_state()
    state["weather_state"] = {
        "risk_flags": [],
        "forecast": [],
        "last_checked": "now",
        "affected_items": [],
    }

    result = await weather_adaptation(state)

    assert result["approval_queue"] == []
    assert result["current_step"] == "create_approvals"


@pytest.mark.asyncio
async def test_weather_adaptation_empty_pool_skips_item() -> None:
    item_dict = _item_to_dict(_mock_item())
    state = _base_state()
    state["weather_state"] = {
        "risk_flags": ["2026-08-02"],
        "forecast": [],
        "last_checked": "now",
        "affected_items": [item_dict],
    }

    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_mock_trip())),
        patch("backend.agents.weather._indoor_candidates", AsyncMock(return_value=[])),
    ):
        result = await weather_adaptation(state)

    assert result["approval_queue"] == []


# ── create_approvals ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_approvals_persists_and_sets_status() -> None:
    state = _base_state()
    state["approval_queue"] = [
        {
            "id": "ap-1",
            "trip_id": "trip-w",
            "proposed_by": "weather_agent",
            "change_type": "weather_replan",
            "summary": "Replace outdoor with indoor",
            "payload": {},
            "status": "pending",
        }
    ]

    with (
        patch("backend.agents.weather._persist_approvals", AsyncMock()) as mock_persist,
        patch("backend.agents.weather._set_trip_awaiting_approval", AsyncMock()) as mock_status,
    ):
        result = await create_approvals(state)

    mock_persist.assert_awaited_once()
    mock_status.assert_awaited_once_with("trip-w")
    assert result["current_step"] == "end"


@pytest.mark.asyncio
async def test_create_approvals_empty_queue_skips_db() -> None:
    state = _base_state()

    with (
        patch("backend.agents.weather._persist_approvals", AsyncMock()) as mock_persist,
        patch("backend.agents.weather._set_trip_awaiting_approval", AsyncMock()) as mock_status,
    ):
        result = await create_approvals(state)

    mock_persist.assert_not_awaited()
    mock_status.assert_not_awaited()
    assert result["current_step"] == "end"


@pytest.mark.asyncio
async def test_create_approvals_ignores_non_weather_approvals() -> None:
    state = _base_state()
    state["approval_queue"] = [
        {
            "id": "ap-2",
            "change_type": "budget_breach",
            "proposed_by": "conflict_detection",
            "summary": "Over budget",
            "payload": {},
            "status": "pending",
        }
    ]

    with (
        patch("backend.agents.weather._persist_approvals", AsyncMock()) as mock_persist,
        patch("backend.agents.weather._set_trip_awaiting_approval", AsyncMock()) as mock_status,
    ):
        await create_approvals(state)

    mock_persist.assert_not_awaited()
    mock_status.assert_not_awaited()
