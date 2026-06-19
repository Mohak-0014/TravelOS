"""Unit tests for the Packing List agent."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.packing_list import _season, run
from backend.graphs.state import TravelOSState

# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_trip(
    trip_id: str = "trip-pl",
    destination_city: str = "Tokyo",
    destination_country: str = "Japan",
    start_date: date = date(2026, 8, 1),
    end_date: date = date(2026, 8, 7),
    num_travelers: int = 2,
) -> MagicMock:
    trip = MagicMock()
    trip.id = trip_id
    trip.destination_city = destination_city
    trip.destination_country = destination_country
    trip.start_date = start_date
    trip.end_date = end_date
    trip.num_travelers = num_travelers
    return trip


def _state(
    trip_id: str = "trip-pl",
    weather_state: dict | None = None,
    itinerary: list | None = None,
) -> TravelOSState:
    return {
        "trip_id": trip_id,
        "user_id": "user-1",
        "traveler_profiles": [],
        "itinerary": itinerary or [],
        "weather_state": weather_state or {},
        "budget_state": {},
        "hotel_state": {},
        "events_state": {},
        "packing_state": {},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "packing_list",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }


_SAMPLE_LLM_RESPONSE = json.dumps(
    {
        "categories": {
            "Documents & Money": ["Passport", "Credit cards"],
            "Clothing": ["T-shirts x3", "Light jacket"],
            "Electronics": ["Phone charger", "Portable battery"],
            "Health & Toiletries": ["Sunscreen SPF50", "Toothbrush"],
            "Accessories": ["Day backpack", "Umbrella"],
            "Destination-Specific": ["IC card for Tokyo transit", "Coin purse"],
        }
    }
)


# ── _season tests ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "month,country,expected_fragment",
    [
        (7, "Japan", "summer"),
        (1, "Japan", "winter"),
        (4, "Japan", "spring"),
        (10, "Japan", "autumn"),
        (1, "Australia", "summer"),  # southern hemisphere — reversed
        (7, "Australia", "winter"),
    ],
)
def test_season(month: int, country: str, expected_fragment: str) -> None:
    result = _season(month, country)
    assert expected_fragment in result.lower()


# ── run() tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_returns_packing_state_on_success() -> None:
    trip = _mock_trip()
    fake_item = MagicMock()
    fake_item.item_type = "activity"
    fake_item.title = "Senso-ji Temple"
    fake_item.day_number = 1

    mock_resp = MagicMock()
    mock_resp.content = _SAMPLE_LLM_RESPONSE

    with (
        patch("backend.agents.packing_list._load_trip", AsyncMock(return_value=trip)),
        patch(
            "backend.agents.packing_list._load_itinerary_items",
            AsyncMock(return_value=[fake_item]),
        ),
        patch("backend.agents.packing_list.build_llm") as mock_build_llm,
        patch("backend.agents.packing_list._persist", AsyncMock()),
    ):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_resp
        mock_build_llm.return_value = mock_llm

        result = await run(_state())

    assert "packing_state" in result
    ps = result["packing_state"]
    assert ps["status"] == "done"  # type: ignore[index]
    cats = ps["categories"]  # type: ignore[index]
    assert "Documents & Money" in cats
    assert "Clothing" in cats
    assert len(cats["Documents & Money"]) == 2


@pytest.mark.asyncio
async def test_run_skips_when_no_trip() -> None:
    with patch("backend.agents.packing_list._load_trip", AsyncMock(return_value=None)):
        result = await run(_state())

    assert result["packing_state"]["status"] == "skipped"  # type: ignore[index]


@pytest.mark.asyncio
async def test_run_handles_llm_error_gracefully() -> None:
    trip = _mock_trip()

    with (
        patch("backend.agents.packing_list._load_trip", AsyncMock(return_value=trip)),
        patch(
            "backend.agents.packing_list._load_itinerary_items",
            AsyncMock(return_value=[]),
        ),
        patch("backend.agents.packing_list.build_llm") as mock_build_llm,
    ):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("LLM timeout")
        mock_build_llm.return_value = mock_llm

        result = await run(_state())

    ps = result["packing_state"]
    assert ps["status"] == "error"  # type: ignore[index]


@pytest.mark.asyncio
async def test_run_strips_markdown_fences() -> None:
    trip = _mock_trip()
    fenced = f"```json\n{_SAMPLE_LLM_RESPONSE}\n```"
    mock_resp = MagicMock()
    mock_resp.content = fenced

    with (
        patch("backend.agents.packing_list._load_trip", AsyncMock(return_value=trip)),
        patch(
            "backend.agents.packing_list._load_itinerary_items",
            AsyncMock(return_value=[]),
        ),
        patch("backend.agents.packing_list.build_llm") as mock_build_llm,
        patch("backend.agents.packing_list._persist", AsyncMock()),
    ):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_resp
        mock_build_llm.return_value = mock_llm

        result = await run(_state())

    assert result["packing_state"]["status"] == "done"  # type: ignore[index]
    assert "Clothing" in result["packing_state"]["categories"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_run_uses_weather_risk_flags() -> None:
    trip = _mock_trip()
    mock_resp = MagicMock()
    mock_resp.content = _SAMPLE_LLM_RESPONSE

    with (
        patch("backend.agents.packing_list._load_trip", AsyncMock(return_value=trip)),
        patch(
            "backend.agents.packing_list._load_itinerary_items",
            AsyncMock(return_value=[]),
        ),
        patch("backend.agents.packing_list.build_llm") as mock_build_llm,
        patch("backend.agents.packing_list._persist", AsyncMock()),
    ):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_resp
        mock_build_llm.return_value = mock_llm

        state = _state(weather_state={"risk_flags": ["heavy_rain", "thunderstorm"]})
        await run(state)

        # Verify the LLM user message includes the risk flags
        call_args = mock_llm.invoke.call_args
        user_msg = call_args[0][0][1].content  # HumanMessage content
        assert "heavy_rain" in user_msg
        assert "thunderstorm" in user_msg
