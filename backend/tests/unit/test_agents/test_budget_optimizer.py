"""Unit tests for the Budget Optimizer agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.budget_optimizer import (
    _OVER_THRESHOLD,
    _UNDER_THRESHOLD,
    _compute_costs,
    _noop,
    _propose_swap,
    _propose_upgrade,
    run,
)
from backend.graphs.state import TravelOSState

# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_trip(
    trip_id: str = "trip-bo",
    budget_total: float | None = 2000.0,
    budget_currency: str = "USD",
    destination_city: str = "Tokyo",
) -> MagicMock:
    trip = MagicMock()
    trip.id = trip_id
    trip.budget_total = budget_total
    trip.budget_currency = budget_currency
    trip.destination_city = destination_city
    trip.flight_origin = None  # opt-in per test — MagicMock default would crash len()
    return trip


def _state(
    trip_id: str = "trip-bo",
    itinerary: list | None = None,
    hotel_state: dict | None = None,
    budget_state: dict | None = None,
) -> TravelOSState:
    return {
        "trip_id": trip_id,
        "user_id": "user-1",
        "traveler_profiles": [],
        "itinerary": itinerary or [],
        "weather_state": {},
        "budget_state": budget_state or {},
        "hotel_state": hotel_state or {},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "budget_optimizer",
        "error_state": None,
        "checkpoint_id": None,
    }


def _itinerary_item(
    item_type: str = "activity",
    est_cost: float | None = 50.0,
) -> dict:
    return {
        "item_type": item_type,
        "title": "Test Item",
        "est_cost": est_cost,
        "day_number": 1,
    }


# ── _compute_costs ────────────────────────────────────────────────────────────


def test_compute_costs_empty_returns_zeros() -> None:
    costs = _compute_costs([], {})
    assert costs == {"lodging": 0.0, "activities": 0.0, "meals": 0.0, "transport": 0.0}


def test_compute_costs_hotel_from_selected() -> None:
    hotel_state = {"selected": {"price_total": 450.0}}
    costs = _compute_costs([], hotel_state)
    assert costs["lodging"] == 450.0
    assert costs["activities"] == 0.0


def test_compute_costs_hotel_none_selected() -> None:
    costs = _compute_costs([], {"selected": None})
    assert costs["lodging"] == 0.0


def test_compute_costs_activity_added() -> None:
    items = [_itinerary_item("activity", 80.0)]
    costs = _compute_costs(items, {})
    assert costs["activities"] == 80.0
    assert costs["meals"] == 0.0


def test_compute_costs_meal_added() -> None:
    items = [_itinerary_item("meal", 35.0)]
    costs = _compute_costs(items, {})
    assert costs["meals"] == 35.0


def test_compute_costs_transport_added() -> None:
    items = [_itinerary_item("transport", 20.0)]
    costs = _compute_costs(items, {})
    assert costs["transport"] == 20.0


def test_compute_costs_zero_cost_ignored() -> None:
    items = [_itinerary_item("activity", 0.0)]
    costs = _compute_costs(items, {})
    assert costs["activities"] == 0.0


def test_compute_costs_none_cost_ignored() -> None:
    items = [_itinerary_item("activity", None)]
    costs = _compute_costs(items, {})
    assert costs["activities"] == 0.0


def test_compute_costs_multiple_categories() -> None:
    items = [
        _itinerary_item("activity", 100.0),
        _itinerary_item("meal", 40.0),
        _itinerary_item("transport", 15.0),
        _itinerary_item("activity", 60.0),
    ]
    hotel_state = {"selected": {"price_total": 300.0}}
    costs = _compute_costs(items, hotel_state)
    assert costs["lodging"] == 300.0
    assert costs["activities"] == 160.0
    assert costs["meals"] == 40.0
    assert costs["transport"] == 15.0


def test_compute_costs_unknown_type_not_counted() -> None:
    items = [_itinerary_item("free", 99.0)]
    costs = _compute_costs(items, {})
    assert sum(costs.values()) == 0.0


# ── _noop ─────────────────────────────────────────────────────────────────────


def test_noop_preserves_existing_budget_state() -> None:
    existing = {"foo": "bar"}
    state = _state(budget_state=existing)
    result = _noop(state)
    assert result["budget_state"] == existing
    assert result["agent_messages"] == []


def test_noop_handles_missing_budget_state() -> None:
    state = _state()
    result = _noop(state)
    assert result["budget_state"] == {}


# ── _propose_swap ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_propose_swap_returns_proposal_on_valid_llm_response() -> None:
    trip = _mock_trip()
    item = {"id": "item-1", "day_number": 2, "title": "Paid Museum", "est_cost": 80.0}
    costs = {"lodging": 500.0, "activities": 200.0, "meals": 100.0, "transport": 50.0}

    llm_response = MagicMock()
    llm_response.content = (
        '{"title": "Free Park", "description": "A lovely park", "reason": "Saves USD 80"}'
    )

    with patch("backend.agents.budget_optimizer.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=llm_response)
        mock_build.return_value = mock_llm

        result = await _propose_swap(trip, item, 0.20, costs)

    assert result is not None
    assert result["change_type"] == "budget_swap"
    assert result["payload"]["current"]["title"] == "Paid Museum"
    assert result["payload"]["replacement"]["title"] == "Free Park"
    assert result["payload"]["day"] == 2


@pytest.mark.asyncio
async def test_propose_swap_returns_none_on_empty_title() -> None:
    trip = _mock_trip()
    item = {"id": "item-1", "day_number": 1, "title": "Tour", "est_cost": 50.0}
    costs = {"lodging": 0.0, "activities": 50.0, "meals": 0.0, "transport": 0.0}

    llm_response = MagicMock()
    llm_response.content = '{"title": "", "description": "desc", "reason": "reason"}'

    with patch("backend.agents.budget_optimizer.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=llm_response)
        mock_build.return_value = mock_llm

        result = await _propose_swap(trip, item, 0.20, costs)

    assert result is None


@pytest.mark.asyncio
async def test_propose_swap_returns_none_on_llm_error() -> None:
    trip = _mock_trip()
    item = {"id": "item-1", "day_number": 1, "title": "Tour", "est_cost": 50.0}
    costs = {"lodging": 0.0, "activities": 50.0, "meals": 0.0, "transport": 0.0}

    with patch("backend.agents.budget_optimizer.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM failed"))
        mock_build.return_value = mock_llm

        result = await _propose_swap(trip, item, 0.20, costs)

    assert result is None


# ── _propose_upgrade ──────────────────────────────────────────────────────────

_FAKE_CANDIDATE = {
    "id": "hotel-cand-1",
    "name": "Grand Ryokan",
    "star_rating": 5.0,
    "price_total": 800.0,
}


@pytest.mark.asyncio
async def test_propose_upgrade_returns_proposal_on_valid_response() -> None:
    trip = _mock_trip(budget_total=3000.0)
    hotel_state = {"selected": {"name": "Business Hotel", "price_total": 300.0, "star_rating": 3.0}}
    costs = {"lodging": 300.0, "activities": 400.0, "meals": 200.0, "transport": 100.0}

    llm_response = MagicMock()
    llm_response.content = (
        '{"title": "Grand Ryokan", "description": "Upgrade to traditional inn", '
        '"reason": "Uses remaining USD 2000 well"}'
    )

    with (
        patch("backend.agents.budget_optimizer._load_upgrade_candidate") as mock_cand,
        patch("backend.agents.budget_optimizer.build_llm") as mock_build,
    ):
        mock_cand.return_value = _FAKE_CANDIDATE
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=llm_response)
        mock_build.return_value = mock_llm

        result = await _propose_upgrade(trip, hotel_state, costs, -0.33)

    assert result is not None
    assert result["change_type"] == "budget_upgrade"
    assert result["payload"]["candidate_id"] == "hotel-cand-1"
    assert result["payload"]["title"] == "Grand Ryokan"
    assert result["payload"]["budget_remaining"] > 0


@pytest.mark.asyncio
async def test_propose_upgrade_returns_none_when_no_candidate() -> None:
    trip = _mock_trip(budget_total=3000.0)

    with patch("backend.agents.budget_optimizer._load_upgrade_candidate") as mock_cand:
        mock_cand.return_value = None
        result = await _propose_upgrade(trip, {}, {}, -0.35)

    assert result is None


@pytest.mark.asyncio
async def test_propose_upgrade_returns_none_on_llm_error() -> None:
    trip = _mock_trip(budget_total=3000.0)

    with (
        patch("backend.agents.budget_optimizer._load_upgrade_candidate") as mock_cand,
        patch("backend.agents.budget_optimizer.build_llm") as mock_build,
    ):
        mock_cand.return_value = _FAKE_CANDIDATE
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        mock_build.return_value = mock_llm

        result = await _propose_upgrade(trip, {}, {}, -0.35)

    assert result is None


# ── run() ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_skips_when_no_budget() -> None:
    state = _state()
    with patch("backend.agents.budget_optimizer._load_trip") as mock_load:
        mock_load.return_value = _mock_trip(budget_total=None)
        result = await run(state)

    assert result["agent_messages"] == []


@pytest.mark.asyncio
async def test_run_skips_when_trip_not_found() -> None:
    state = _state()
    with patch("backend.agents.budget_optimizer._load_trip") as mock_load:
        mock_load.return_value = None
        result = await run(state)

    assert result["agent_messages"] == []


@pytest.mark.asyncio
async def test_run_skips_when_zero_cost_data() -> None:
    state = _state(itinerary=[])
    with patch("backend.agents.budget_optimizer._load_trip") as mock_load:
        mock_load.return_value = _mock_trip(budget_total=2000.0)
        result = await run(state)

    assert "budget_state" in result
    assert result["agent_messages"] == []


@pytest.mark.asyncio
async def test_run_on_track_returns_budget_summary() -> None:
    items = [
        _itinerary_item("activity", 100.0),
        _itinerary_item("meal", 50.0),
    ]
    hotel_state = {"selected": {"price_total": 500.0}}
    # Total = 650 vs budget 700 → deviation -7.1% → on_track (between -30% and +15%)
    state = _state(itinerary=items, hotel_state=hotel_state)

    with patch("backend.agents.budget_optimizer._load_trip") as mock_load:
        # Unmapped city -> local currency USD == budget currency -> costs pass through
        mock_load.return_value = _mock_trip(budget_total=700.0, destination_city="Springfield")
        result = await run(state)

    bs = result["budget_state"]
    assert bs["status"] == "on_track"
    assert bs["total_planned"] == pytest.approx(650.0)
    assert bs["budget_total"] == 700.0
    assert bs["proposals_created"] == 0


@pytest.mark.asyncio
async def test_run_over_budget_creates_swap_proposals() -> None:
    items = [
        _itinerary_item("activity", 600.0),
        _itinerary_item("activity", 400.0),
        _itinerary_item("meal", 200.0),
    ]
    hotel_state = {"selected": {"price_total": 800.0}}
    # Total = 2000 vs budget 1500 → 33% over
    state = _state(itinerary=items, hotel_state=hotel_state)

    fake_db_items = [{"id": "x", "day_number": 1, "title": "X", "est_cost": 600.0}]
    fake_proposal = {
        "proposed_by": "budget_optimizer",
        "change_type": "budget_swap",
        "summary": "Replace X with Y",
        "payload": {
            "item_id": "x",
            "day": 1,
            "current": {"id": "x", "title": "X"},
            "replacement": {"title": "Y", "description": ""},
            "reason": "Saves $",
            "est_cost_original": 600.0,
            "currency": "USD",
        },
    }

    with (
        patch("backend.agents.budget_optimizer._load_trip") as mock_load,
        patch("backend.agents.budget_optimizer._load_expensive_activities") as mock_items,
        patch("backend.agents.budget_optimizer._propose_swap") as mock_swap,
        patch("backend.agents.budget_optimizer._persist_approvals") as mock_persist,
        patch("backend.agents.budget_optimizer._set_trip_awaiting_approval") as mock_status,
    ):
        mock_load.return_value = _mock_trip(budget_total=1500.0, destination_city="Springfield")
        mock_items.return_value = fake_db_items  # auto-AsyncMock wraps this
        mock_swap.return_value = fake_proposal  # auto-AsyncMock wraps this
        mock_persist.return_value = None
        mock_status.return_value = None

        result = await run(state)

    bs = result["budget_state"]
    assert bs["status"] == "over_budget"
    assert bs["deviation_pct"] > _OVER_THRESHOLD * 100


@pytest.mark.asyncio
async def test_run_under_budget_creates_upgrade_proposal() -> None:
    items = [_itinerary_item("activity", 100.0)]
    hotel_state = {"selected": {"price_total": 200.0}}
    # Total = 300 vs budget 1500 → 80% under
    state = _state(itinerary=items, hotel_state=hotel_state)

    fake_upgrade = {
        "proposed_by": "budget_optimizer",
        "change_type": "budget_upgrade",
        "summary": "Premium upgrade",
        "payload": {
            "title": "Luxury Experience",
            "description": "",
            "reason": "Uses budget well",
            "budget_remaining": 1200.0,
            "currency": "USD",
        },
    }

    with (
        patch("backend.agents.budget_optimizer._load_trip") as mock_load,
        patch("backend.agents.budget_optimizer._propose_upgrade") as mock_upgrade,
        patch("backend.agents.budget_optimizer._persist_approvals") as mock_persist,
        patch("backend.agents.budget_optimizer._set_trip_awaiting_approval") as mock_status,
    ):
        mock_load.return_value = _mock_trip(budget_total=1500.0)
        mock_upgrade.return_value = fake_upgrade
        mock_persist.return_value = AsyncMock(return_value=None)()
        mock_status.return_value = AsyncMock(return_value=None)()

        result = await run(state)

    bs = result["budget_state"]
    assert bs["status"] == "under_budget"
    assert bs["deviation_pct"] < _UNDER_THRESHOLD * 100


@pytest.mark.asyncio
async def test_run_handles_exception_gracefully() -> None:
    state = _state()
    with patch("backend.agents.budget_optimizer._load_trip", side_effect=RuntimeError("db down")):
        result = await run(state)

    assert "budget_state" in result
    assert result["agent_messages"] == []


# ── Flight cost inclusion ─────────────────────────────────────────────────────


def _flight_offer(price: float = 400.0, currency: str = "USD"):
    from backend.tools.flights import FlightOffer

    return FlightOffer(
        origin="DEL",
        destination="COK",
        departure_date="2026-08-01",
        return_date="2026-08-05",
        airline="AI",
        price_total=price,
        price_currency=currency,
        cabin="ECONOMY",
        duration_outbound="3h 10m",
    )


@pytest.mark.asyncio
async def test_run_includes_cheapest_flight_in_budget() -> None:
    items = [_itinerary_item("activity", 100.0)]
    hotel_state = {"selected": {"price_total": 500.0}}
    state = _state(itinerary=items, hotel_state=hotel_state)
    trip = _mock_trip(budget_total=2000.0, destination_city="Springfield")
    trip.flight_origin = "DEL"
    trip.start_date = MagicMock()
    trip.end_date = MagicMock()
    trip.num_travelers = 2

    offers = [_flight_offer(450.0), _flight_offer(300.0), _flight_offer(500.0)]
    with (
        patch("backend.agents.budget_optimizer._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.budget_optimizer.search_flights", new=AsyncMock(return_value=offers)),
        patch(
            "backend.agents.budget_optimizer.get_redis_client",
            return_value=MagicMock(aclose=AsyncMock()),
        ),
    ):
        result = await run(state)

    bs = result["budget_state"]
    assert bs["by_category"]["flights"] == 300.0  # cheapest offer, already USD
    # 100 activity + 500 hotel + 300 flights
    assert bs["total_planned"] == pytest.approx(900.0)


@pytest.mark.asyncio
async def test_run_no_flight_origin_excludes_flights() -> None:
    items = [_itinerary_item("activity", 100.0)]
    hotel_state = {"selected": {"price_total": 500.0}}
    state = _state(itinerary=items, hotel_state=hotel_state)
    trip = _mock_trip(budget_total=2000.0, destination_city="Springfield")  # flight_origin=None

    with patch("backend.agents.budget_optimizer._load_trip", new=AsyncMock(return_value=trip)):
        result = await run(state)

    assert "flights" not in result["budget_state"]["by_category"]


@pytest.mark.asyncio
async def test_run_flight_search_failure_excludes_flights() -> None:
    # Real fare or nothing — an errored search must not fabricate a number
    items = [_itinerary_item("activity", 100.0)]
    hotel_state = {"selected": {"price_total": 500.0}}
    state = _state(itinerary=items, hotel_state=hotel_state)
    trip = _mock_trip(budget_total=2000.0, destination_city="Springfield")
    trip.flight_origin = "DEL"
    trip.start_date = MagicMock()
    trip.end_date = MagicMock()
    trip.num_travelers = 2

    with (
        patch("backend.agents.budget_optimizer._load_trip", new=AsyncMock(return_value=trip)),
        patch(
            "backend.agents.budget_optimizer.search_flights",
            new=AsyncMock(side_effect=RuntimeError("duffel down")),
        ),
        patch(
            "backend.agents.budget_optimizer.get_redis_client",
            return_value=MagicMock(aclose=AsyncMock()),
        ),
    ):
        result = await run(state)

    assert "flights" not in result["budget_state"]["by_category"]
    assert result["budget_state"]["total_planned"] == pytest.approx(600.0)


# ── Budget state persistence (durable copy for the API) ────────────────────────


@pytest.mark.asyncio
async def test_run_persists_budget_state_to_trip_row() -> None:
    items = [_itinerary_item("activity", 100.0)]
    hotel_state = {"selected": {"price_total": 500.0}}
    state = _state(itinerary=items, hotel_state=hotel_state)
    trip = _mock_trip(budget_total=2000.0, destination_city="Springfield")

    with (
        patch("backend.agents.budget_optimizer._load_trip", new=AsyncMock(return_value=trip)),
        patch(
            "backend.agents.budget_optimizer._persist_budget_state", new=AsyncMock()
        ) as mock_persist,
    ):
        result = await run(state)

    mock_persist.assert_awaited_once()
    trip_id_arg, persisted = mock_persist.await_args.args
    assert trip_id_arg == "trip-bo"
    assert persisted["by_category"]["lodging"] == 500.0
    assert persisted["total_planned"] == pytest.approx(600.0)
    assert persisted == result["budget_state"]
