import pytest
from langchain_core.messages import SystemMessage

from backend.agents.supervisor import run
from backend.graphs.state import TravelOSState


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-abc",
        "user_id": "user-xyz",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {},
        "hotel_state": {},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "supervisor",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


# ── fresh run ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fresh_run_routes_to_travel_style() -> None:
    result = await run(_base_state())
    assert result["current_step"] == "travel_style"


@pytest.mark.asyncio
async def test_fresh_run_adds_system_message() -> None:
    result = await run(_base_state())
    messages = result["agent_messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], SystemMessage)
    assert "trip-abc" in messages[0].content


@pytest.mark.asyncio
async def test_fresh_run_initializes_empty_budget_state() -> None:
    result = await run(_base_state(budget_state={}))
    bs = result["budget_state"]
    assert bs["spent"] == 0.0
    assert "by_category" in bs
    assert bs["breach_pct"] == 0.0


@pytest.mark.asyncio
async def test_fresh_run_initializes_empty_weather_state() -> None:
    result = await run(_base_state(weather_state={}))
    ws = result["weather_state"]
    assert ws["risk_flags"] == []
    assert ws["last_checked"] is None


@pytest.mark.asyncio
async def test_fresh_run_initializes_empty_hotel_state() -> None:
    result = await run(_base_state(hotel_state={}))
    hs = result["hotel_state"]
    assert hs["candidates"] == []
    assert hs["selected"] is None


@pytest.mark.asyncio
async def test_fresh_run_does_not_overwrite_existing_sub_states() -> None:
    existing_budget = {"total": 5000.0, "spent": 200.0, "by_category": {}, "breach_pct": 4.0}
    existing_weather = {"risk_flags": ["rain"], "last_checked": "2026-06-11"}
    result = await run(_base_state(budget_state=existing_budget, weather_state=existing_weather))
    assert "budget_state" not in result
    assert "weather_state" not in result


@pytest.mark.asyncio
async def test_fresh_run_budget_categories_match_optimizer_vocabulary() -> None:
    # Must stay in sync with budget_optimizer._compute_costs keys
    result = await run(_base_state(budget_state={}))
    assert set(result["budget_state"]["by_category"]) == {
        "lodging",
        "activities",
        "meals",
        "transport",
    }


@pytest.mark.asyncio
async def test_fresh_run_initializes_replan_feedback() -> None:
    result = await run(_base_state())
    assert result["replan_feedback"] == []
