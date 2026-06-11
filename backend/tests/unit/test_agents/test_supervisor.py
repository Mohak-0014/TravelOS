from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, SystemMessage

from backend.agents.supervisor import _parse_recovery_decision, run
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


# ── error recovery — max retries ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_error_recovery_aborts_at_max_retries() -> None:
    state = _base_state(
        error_state={"node": "itinerary_planner", "message": "timeout"},
        replan_iterations=3,
    )
    result = await run(state)
    assert result["current_step"] == "end"
    assert "max retries" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_error_recovery_aborts_when_above_max_retries() -> None:
    state = _base_state(
        error_state={"node": "hotel_agent", "message": "crash"},
        replan_iterations=5,
    )
    result = await run(state)
    assert result["current_step"] == "end"


# ── error recovery — LLM-assisted ─────────────────────────────────────────────


def _mock_llm(content: str) -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return mock_llm


@pytest.mark.asyncio
async def test_error_recovery_retries_on_recoverable_error() -> None:
    llm_response = (
        '{"recoverable": true, "retry_node": "itinerary_planner", "reason": "rate limit"}'
    )
    state = _base_state(
        error_state={"node": "itinerary_planner", "message": "rate limit"},
        replan_iterations=0,
    )
    with patch("backend.agents.supervisor._build_llm", return_value=_mock_llm(llm_response)):
        result = await run(state)

    assert result["current_step"] == "itinerary_planner"
    assert result["error_state"] is None
    assert result["replan_iterations"] == 1


@pytest.mark.asyncio
async def test_error_recovery_increments_replan_iterations() -> None:
    llm_response = '{"recoverable": true, "retry_node": "travel_style", "reason": "timeout"}'
    state = _base_state(
        error_state={"node": "travel_style", "message": "timeout"},
        replan_iterations=1,
    )
    with patch("backend.agents.supervisor._build_llm", return_value=_mock_llm(llm_response)):
        result = await run(state)

    assert result["replan_iterations"] == 2


@pytest.mark.asyncio
async def test_error_recovery_ends_on_unrecoverable_error() -> None:
    llm_response = (
        '{"recoverable": false, "retry_node": "itinerary_planner", "reason": "missing trip_id"}'
    )
    state = _base_state(
        error_state={"node": "supervisor", "message": "missing trip_id"},
        replan_iterations=0,
    )
    with patch("backend.agents.supervisor._build_llm", return_value=_mock_llm(llm_response)):
        result = await run(state)

    assert result["current_step"] == "end"
    assert result["replan_iterations"] == 3


@pytest.mark.asyncio
async def test_error_recovery_falls_back_on_invalid_retry_node() -> None:
    llm_response = '{"recoverable": true, "retry_node": "nonexistent_node", "reason": "timeout"}'
    state = _base_state(
        error_state={"node": "hotel_agent", "message": "timeout"},
        replan_iterations=0,
    )
    with patch("backend.agents.supervisor._build_llm", return_value=_mock_llm(llm_response)):
        result = await run(state)

    assert result["current_step"] == "itinerary_planner"


# ── _parse_recovery_decision (pure function) ──────────────────────────────────


def test_parse_valid_json() -> None:
    raw = '{"recoverable": true, "retry_node": "hotel_agent", "reason": "rate limit"}'
    d = _parse_recovery_decision(raw)
    assert d["recoverable"] is True
    assert d["retry_node"] == "hotel_agent"
    assert d["reason"] == "rate limit"


def test_parse_json_embedded_in_prose() -> None:
    raw = (
        'Sure, here is my decision: {"recoverable": false, "retry_node": "travel_style",'
        ' "reason": "missing data"} Thank you.'
    )
    d = _parse_recovery_decision(raw)
    assert d["recoverable"] is False


def test_parse_invalid_json_returns_fallback() -> None:
    d = _parse_recovery_decision("not valid json at all")
    assert d["recoverable"] is False
    assert d["retry_node"] == "itinerary_planner"
    assert "failed to parse" in d["reason"]


def test_parse_empty_string_returns_fallback() -> None:
    d = _parse_recovery_decision("")
    assert d["recoverable"] is False
