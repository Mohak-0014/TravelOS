from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import SystemMessage

from backend.graphs.approval_gate import run
from backend.graphs.state import TravelOSState

# ── helpers ───────────────────────────────────────────────────────────────────


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-ag",
        "user_id": "user-ag",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {"total": 1000.0, "spent": 0.0, "by_category": {}, "breach_pct": 0.0},
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "approval_gate",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _approval(
    approval_id: str = "appr-1",
    change_type: str = "budget_exceed",
    status: str = "pending",
) -> dict:  # type: ignore[type-arg]
    return {
        "id": approval_id,
        "proposed_by": "conflict_detection",
        "change_type": change_type,
        "summary": "Cost 20% over budget",
        "payload": {"estimated_total": 1200.0, "budget_total": 1000.0},
        "status": status,
    }


def _make_session_mock(existing_record=None):
    """Return (session_mock, ctx_mock) with session.get returning existing_record."""
    session = AsyncMock()
    session.get.return_value = existing_record
    session.add = MagicMock()
    session.commit = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = False
    return session, ctx


# ── empty queue ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_empty_queue_routes_to_checkpoint_save() -> None:
    result = await run(_base_state())
    assert result["current_step"] == "checkpoint_save"


@pytest.mark.asyncio
async def test_run_empty_queue_message_says_no_approvals_required() -> None:
    result = await run(_base_state())
    msg = result["agent_messages"][0]
    assert isinstance(msg, SystemMessage)
    assert "no approvals required" in msg.content.lower()


@pytest.mark.asyncio
async def test_run_always_routes_to_checkpoint_save() -> None:
    _, ctx = _make_session_mock(existing_record=None)
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(approval_queue=[_approval()]))
    assert result["current_step"] == "checkpoint_save"


# ── DB persistence ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_persists_new_approval_to_db() -> None:
    session, ctx = _make_session_mock(existing_record=None)
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(approval_queue=[_approval("appr-new")]))
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_skips_existing_approval() -> None:
    existing = MagicMock()
    session, ctx = _make_session_mock(existing_record=existing)
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(approval_queue=[_approval("appr-exists")]))
    session.add.assert_not_called()
    assert "already in DB" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_multiple_approvals_all_new_all_persisted() -> None:
    session, ctx = _make_session_mock(existing_record=None)
    approvals = [_approval("a1"), _approval("a2"), _approval("a3")]
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(approval_queue=approvals))
    assert session.add.call_count == 3


@pytest.mark.asyncio
async def test_run_partial_persist_when_some_exist() -> None:
    # First call returns None (new), second returns existing record
    existing = MagicMock()
    session = AsyncMock()
    session.get.side_effect = [None, existing]
    session.add = MagicMock()
    session.commit = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = False

    approvals = [_approval("a-new"), _approval("a-exists")]
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(approval_queue=approvals))

    assert session.add.call_count == 1
    assert "1 persisted" in result["agent_messages"][0].content
    assert "1 already in DB" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_item_without_id_is_skipped() -> None:
    session, ctx = _make_session_mock()
    bad_item = {
        "proposed_by": "x",
        "change_type": "x",
        "summary": "",
        "payload": {},
        "status": "pending",
    }
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(approval_queue=[bad_item]))
    session.add.assert_not_called()
    # Still routes onward
    assert result["current_step"] == "checkpoint_save"


# ── DB error degradation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_db_error_degrades_gracefully() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    ctx = AsyncMock()
    ctx.__aenter__.side_effect = SQLAlchemyError("connection refused")

    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(approval_queue=[_approval()]))

    # Should not raise; should still proceed
    assert result["current_step"] == "checkpoint_save"


# ── message content ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_message_contains_trip_id() -> None:
    result = await run(_base_state())
    assert "trip-ag" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_adds_system_message_instance() -> None:
    result = await run(_base_state())
    assert isinstance(result["agent_messages"][0], SystemMessage)


@pytest.mark.asyncio
async def test_run_message_reports_count_when_approvals_present() -> None:
    session, ctx = _make_session_mock(existing_record=None)
    approvals = [_approval("a1"), _approval("a2")]
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        result = await run(_base_state(approval_queue=approvals))
    assert "2 approval(s)" in result["agent_messages"][0].content


# ── Approval DB record fields ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_persisted_approval_has_correct_fields() -> None:
    from backend.db.models import Approval

    session, ctx = _make_session_mock(existing_record=None)
    appr = _approval("appr-check")
    with patch("backend.graphs.approval_gate.AsyncSessionLocal", return_value=ctx):
        await run(_base_state(trip_id="trip-field-check", approval_queue=[appr]))

    call_args = session.add.call_args[0][0]
    assert isinstance(call_args, Approval)
    assert call_args.id == "appr-check"
    assert call_args.trip_id == "trip-field-check"
    assert call_args.change_type == "budget_exceed"
    assert call_args.status == "pending"
