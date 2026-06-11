"""
End-to-end test for the weather replan graph.

Runs all 4 nodes (weather_check → impact_assessment → weather_adaptation →
create_approvals) with mocked external I/O (DB, LLM, HTTP) and asserts the
final LangGraph state is correct.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from backend.graphs.replan_graph import build_replan_graph
from backend.graphs.state import TravelOSState
from backend.tools.weather import WeatherDay

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_trip(city: str = "Rome") -> MagicMock:
    t = MagicMock()
    t.id = "trip-e2e"
    t.user_id = "user-e2e"
    t.destination_city = city
    t.destination_country = "IT"
    t.start_date = date(2026, 8, 1)
    t.end_date = date(2026, 8, 5)
    t.latitude = 41.9
    t.longitude = 12.5
    return t


def _make_weather_day(d: str, is_adverse: bool, label: str = "Heavy rain") -> WeatherDay:
    return WeatherDay(
        date=date.fromisoformat(d),
        temp_min_c=14.0,
        temp_max_c=21.0,
        precipitation_mm=30.0,
        precipitation_prob=90,
        condition_code=65,
        condition_label=label,
        is_adverse=is_adverse,
    )


def _make_outdoor_item(item_date: str = "2026-08-02") -> dict:  # type: ignore[type-arg]
    return {
        "id": "item-outdoor-1",
        "trip_id": "trip-e2e",
        "day_number": 2,
        "item_date": item_date,
        "start_time": "10:00",
        "end_time": "12:00",
        "item_type": "activity",
        "title": "Colosseum Tour",
        "description": "Walking tour of the Colosseum ruins.",
        "latitude": 41.89,
        "longitude": 12.49,
        "address": "Piazza del Colosseo, Rome",
        "source_provider": "overpass",
        "source_ref": "way/987",
        "est_cost": 18.0,
        "est_cost_currency": "EUR",
        "is_outdoor": True,
        "sort_order": 1,
    }


def _initial_state() -> TravelOSState:
    return {  # type: ignore[return-value]
        "trip_id": "trip-e2e",
        "user_id": "user-e2e",
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


# ── e2e: adverse weather → approval created ───────────────────────────────────


@pytest.mark.asyncio
async def test_replan_graph_e2e_adverse_weather_creates_approval() -> None:
    """
    Full graph run: adverse weather on day 2 affects one outdoor item.
    Expects one weather_replan approval in the final state.
    """
    weather_days = [
        _make_weather_day("2026-08-01", is_adverse=False, label="Clear sky"),
        _make_weather_day("2026-08-02", is_adverse=True, label="Heavy rain"),
        _make_weather_day("2026-08-03", is_adverse=False, label="Partly cloudy"),
    ]
    outdoor_item = _make_outdoor_item("2026-08-02")
    indoor_alternative = {
        "title": "Vatican Museums",
        "description": "World-class art collection housed indoors.",
        "item_type": "activity",
        "is_outdoor": False,
    }

    persisted_approvals: list[dict] = []  # type: ignore[type-arg]

    async def _capture_persist(trip_id: str, approvals: list) -> None:  # type: ignore[type-arg]
        persisted_approvals.extend(approvals)

    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_make_trip())),
        patch("backend.agents.weather._resolve_coords", AsyncMock(return_value=(41.9, 12.5))),
        patch("backend.agents.weather.fetch_weather", AsyncMock(return_value=weather_days)),
        patch("backend.agents.weather._save_weather_snapshots", AsyncMock()),
        patch(
            "backend.agents.weather._load_affected_items", AsyncMock(return_value=[outdoor_item])
        ),
        patch(
            "backend.agents.weather._generate_alternative",
            AsyncMock(return_value=indoor_alternative),
        ),
        patch("backend.agents.weather._persist_approvals", AsyncMock(side_effect=_capture_persist)),
        patch("backend.agents.weather._set_trip_awaiting_approval", AsyncMock()),
    ):
        graph = build_replan_graph(checkpointer=MemorySaver())
        final_state = await graph.ainvoke(
            _initial_state(), {"configurable": {"thread_id": "e2e-1"}}
        )

    # weather_state populated by weather_check
    ws = final_state["weather_state"]
    assert "2026-08-02" in ws["risk_flags"]
    assert "2026-08-01" not in ws["risk_flags"]
    assert len(ws["forecast"]) == 3
    assert ws["last_checked"] is not None

    # approval_queue populated by weather_adaptation
    queue: list[dict] = final_state["approval_queue"]  # type: ignore[type-arg]
    assert len(queue) == 1
    approval = queue[0]
    assert approval["change_type"] == "weather_replan"
    assert approval["proposed_by"] == "weather_agent"
    assert "Colosseum Tour" in approval["summary"]
    assert "Vatican Museums" in approval["summary"]
    assert approval["payload"]["original_item"]["title"] == "Colosseum Tour"
    assert approval["payload"]["alternative_item"]["title"] == "Vatican Museums"
    assert approval["payload"]["alternative_item"]["is_outdoor"] is False
    assert approval["payload"]["alternative_item"]["day_number"] == 2
    assert approval["payload"]["weather_condition"] == "Heavy rain"
    assert approval["status"] == "pending"

    # approval was persisted to DB
    assert len(persisted_approvals) == 1
    assert persisted_approvals[0]["change_type"] == "weather_replan"

    # all 4 nodes left messages
    messages = final_state["agent_messages"]
    contents = [str(m.content) for m in messages]
    assert any("forecast" in c.lower() or "fetched" in c.lower() for c in contents)
    assert any("outdoor" in c.lower() or "affected" in c.lower() for c in contents)
    assert any("proposed" in c.lower() or "alternative" in c.lower() for c in contents)


# ── e2e: no adverse weather → no approvals ───────────────────────────────────


@pytest.mark.asyncio
async def test_replan_graph_e2e_clear_weather_no_approvals() -> None:
    """
    Full graph run: no adverse weather.
    Expects graph completes cleanly with empty approval_queue.
    """
    clear_days = [
        _make_weather_day("2026-08-01", is_adverse=False, label="Clear sky"),
        _make_weather_day("2026-08-02", is_adverse=False, label="Mainly clear"),
    ]

    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_make_trip())),
        patch("backend.agents.weather._resolve_coords", AsyncMock(return_value=(41.9, 12.5))),
        patch("backend.agents.weather.fetch_weather", AsyncMock(return_value=clear_days)),
        patch("backend.agents.weather._save_weather_snapshots", AsyncMock()),
        patch("backend.agents.weather._load_affected_items", AsyncMock(return_value=[])),
        patch("backend.agents.weather._persist_approvals", AsyncMock()) as mock_persist,
        patch("backend.agents.weather._set_trip_awaiting_approval", AsyncMock()) as mock_status,
    ):
        graph = build_replan_graph(checkpointer=MemorySaver())
        final_state = await graph.ainvoke(
            _initial_state(), {"configurable": {"thread_id": "e2e-2"}}
        )

    assert final_state["weather_state"]["risk_flags"] == []
    assert final_state["approval_queue"] == []
    mock_persist.assert_not_awaited()
    mock_status.assert_not_awaited()


# ── e2e: trip not found → graph completes gracefully ─────────────────────────


@pytest.mark.asyncio
async def test_replan_graph_e2e_trip_not_found_completes_gracefully() -> None:
    """
    Full graph run when the trip doesn't exist in DB.
    Expects graceful completion with empty state — no exceptions raised.
    """
    with patch("backend.agents.weather._load_trip", AsyncMock(return_value=None)):
        graph = build_replan_graph(checkpointer=MemorySaver())
        final_state = await graph.ainvoke(
            _initial_state(), {"configurable": {"thread_id": "e2e-3"}}
        )

    assert final_state["approval_queue"] == []
    assert final_state["weather_state"]["risk_flags"] == []


# ── e2e: multiple adverse days, multiple outdoor items ────────────────────────


@pytest.mark.asyncio
async def test_replan_graph_e2e_multiple_affected_items() -> None:
    """
    Two outdoor items on two different adverse days → two approvals.
    """
    weather_days = [
        _make_weather_day("2026-08-02", is_adverse=True, label="Thunderstorm"),
        _make_weather_day("2026-08-04", is_adverse=True, label="Heavy snow"),
    ]
    outdoor_items = [
        _make_outdoor_item("2026-08-02"),
        {
            **_make_outdoor_item("2026-08-04"),
            "id": "item-outdoor-2",
            "day_number": 4,
            "title": "Park Walk",
        },
    ]

    call_count = 0

    async def _alt_by_index(item: dict, city: str) -> dict:  # type: ignore[type-arg]
        nonlocal call_count
        call_count += 1
        return {
            "title": f"Indoor Option {call_count}",
            "description": "A great indoor activity.",
            "item_type": "activity",
            "is_outdoor": False,
        }

    with (
        patch("backend.agents.weather._load_trip", AsyncMock(return_value=_make_trip())),
        patch("backend.agents.weather._resolve_coords", AsyncMock(return_value=(41.9, 12.5))),
        patch("backend.agents.weather.fetch_weather", AsyncMock(return_value=weather_days)),
        patch("backend.agents.weather._save_weather_snapshots", AsyncMock()),
        patch("backend.agents.weather._load_affected_items", AsyncMock(return_value=outdoor_items)),
        patch("backend.agents.weather._generate_alternative", AsyncMock(side_effect=_alt_by_index)),
        patch("backend.agents.weather._persist_approvals", AsyncMock()),
        patch("backend.agents.weather._set_trip_awaiting_approval", AsyncMock()),
    ):
        graph = build_replan_graph(checkpointer=MemorySaver())
        final_state = await graph.ainvoke(
            _initial_state(), {"configurable": {"thread_id": "e2e-4"}}
        )

    assert len(final_state["weather_state"]["risk_flags"]) == 2
    assert len(final_state["approval_queue"]) == 2
    titles = [a["payload"]["alternative_item"]["title"] for a in final_state["approval_queue"]]
    assert "Indoor Option 1" in titles
    assert "Indoor Option 2" in titles
