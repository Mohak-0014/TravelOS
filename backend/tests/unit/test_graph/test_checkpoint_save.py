from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import SystemMessage

from backend.graphs.checkpoint_save import run
from backend.graphs.state import TravelOSState

# ── helpers ───────────────────────────────────────────────────────────────────


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-cs",
        "user_id": "user-cs",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {"total": 1000.0, "spent": 0.0, "by_category": {}, "breach_pct": 0.0},
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "checkpoint_save",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _config(thread_id: str | None = "thread-123") -> dict:  # type: ignore[type-arg]
    if thread_id is None:
        return {}
    return {"configurable": {"thread_id": thread_id}}


def _pending_approval() -> dict:  # type: ignore[type-arg]
    return {
        "id": "appr-pending",
        "proposed_by": "conflict_detection",
        "change_type": "budget_exceed",
        "summary": "Over budget",
        "payload": {},
        "status": "pending",
    }


def _make_trip_mock(trip_id: str = "trip-cs") -> MagicMock:
    trip = MagicMock()
    trip.id = trip_id
    trip.status = "planning"
    trip.langgraph_thread_id = None
    return trip


def _make_execute_result(has_pending: bool = False) -> MagicMock:
    """Return a mock scalars().first() chain for the Approval query."""
    first_value = MagicMock() if has_pending else None
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = first_value
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def _make_session_mock(
    trip: MagicMock | None = None,
    has_pending_approval: bool = False,
):
    session = AsyncMock()
    session.get.return_value = trip
    session.execute = AsyncMock(return_value=_make_execute_result(has_pending_approval))
    session.commit = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = False
    return session, ctx


# ── status logic ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_sets_status_planned_when_no_pending() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip, has_pending_approval=False)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(), _config())
    assert trip.status == "planned"


@pytest.mark.asyncio
async def test_run_sets_status_awaiting_approval_when_pending_exists() -> None:
    trip = _make_trip_mock()
    # DB query returns a pending approval — status must become awaiting_approval
    session, ctx = _make_session_mock(trip, has_pending_approval=True)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(), _config())
    assert trip.status == "awaiting_approval"


@pytest.mark.asyncio
async def test_run_sets_status_planned_when_no_db_pending() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip, has_pending_approval=False)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(approval_queue=[_pending_approval()]), _config())
    # approval_queue is ignored — DB result (no pending) determines status
    assert trip.status == "planned"


# ── thread_id / checkpoint_ref ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_writes_thread_id_to_trip() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(), _config("t-xyz"))
    assert trip.langgraph_thread_id == "t-xyz"


@pytest.mark.asyncio
async def test_run_writes_thread_id_to_state() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config("t-abc"))
    assert result["run_checkpoint_ref"] == "t-abc"


@pytest.mark.asyncio
async def test_run_checkpoint_ref_none_when_no_thread_id() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config(thread_id=None))
    assert result["run_checkpoint_ref"] is None


@pytest.mark.asyncio
async def test_run_does_not_set_thread_id_when_absent() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(), _config(thread_id=None))
    assert trip.langgraph_thread_id is None


# ── trip not found ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_handles_trip_not_found() -> None:
    session, ctx = _make_session_mock(trip=None)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config())
    # Should not raise; still returns a valid result
    assert result["current_step"] == "end"


@pytest.mark.asyncio
async def test_run_does_not_commit_when_trip_not_found() -> None:
    session, ctx = _make_session_mock(trip=None)
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(), _config())
    session.commit.assert_not_awaited()


# ── DB error degradation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_db_error_degrades_gracefully() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    ctx = AsyncMock()
    ctx.__aenter__.side_effect = SQLAlchemyError("timeout")

    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config())

    assert result["current_step"] == "end"


# ── routing and message ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_always_routes_to_end() -> None:
    session, ctx = _make_session_mock(_make_trip_mock())
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config())
    assert result["current_step"] == "end"


@pytest.mark.asyncio
async def test_run_adds_system_message() -> None:
    session, ctx = _make_session_mock(_make_trip_mock())
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config())
    assert isinstance(result["agent_messages"][0], SystemMessage)


@pytest.mark.asyncio
async def test_run_message_contains_trip_id() -> None:
    session, ctx = _make_session_mock(_make_trip_mock())
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config())
    assert "trip-cs" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_message_contains_status() -> None:
    session, ctx = _make_session_mock(_make_trip_mock())
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config())
    assert "planned" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_message_contains_thread_id_when_present() -> None:
    session, ctx = _make_session_mock(_make_trip_mock())
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), _config("thread-show-me"))
    assert "thread-show-me" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_no_config_still_proceeds() -> None:
    session, ctx = _make_session_mock(_make_trip_mock())
    with patch("backend.graphs.checkpoint_save.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(), config=None)
    assert result["current_step"] == "end"
    assert result["run_checkpoint_ref"] is None
