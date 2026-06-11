from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.workflows.celery_tasks import (
    _persist_pending_approvals,
    _run_trip_graph,
    _set_trip_status,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_trip_mock() -> MagicMock:
    trip = MagicMock()
    trip.status = "planning"
    trip.langgraph_thread_id = None
    return trip


def _make_session_mock(trip: MagicMock | None = None):
    session = AsyncMock()
    session.get.return_value = trip
    session.add = MagicMock()
    session.commit = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = False
    return session, ctx


def _make_snapshot(approval_queue: list | None = None) -> MagicMock:
    snapshot = MagicMock()
    snapshot.values = {"approval_queue": approval_queue or []}
    return snapshot


def _make_graph_mock(snapshot: MagicMock | None = None) -> AsyncMock:
    graph = AsyncMock()
    graph.ainvoke = AsyncMock(return_value={})
    graph.aget_state = AsyncMock(return_value=snapshot or _make_snapshot())
    return graph


def _pending_approval(approval_id: str = "appr-1") -> dict:  # type: ignore[type-arg]
    return {
        "id": approval_id,
        "proposed_by": "conflict_detection",
        "change_type": "budget_exceed",
        "summary": "20% over budget",
        "payload": {"estimated_total": 1200.0, "budget_total": 1000.0},
        "status": "pending",
    }


# ── _set_trip_status ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_trip_status_updates_trip() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip)
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _set_trip_status("trip-1", "generating")
    assert trip.status == "generating"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_trip_status_writes_thread_id_when_given() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip)
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _set_trip_status("trip-1", "generating", thread_id="t-xyz")
    assert trip.langgraph_thread_id == "t-xyz"


@pytest.mark.asyncio
async def test_set_trip_status_no_thread_id_leaves_field_alone() -> None:
    trip = _make_trip_mock()
    session, ctx = _make_session_mock(trip)
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _set_trip_status("trip-1", "generating", thread_id=None)
    assert trip.langgraph_thread_id is None


@pytest.mark.asyncio
async def test_set_trip_status_handles_missing_trip() -> None:
    session, ctx = _make_session_mock(trip=None)
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _set_trip_status("trip-missing", "generating")
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_trip_status_handles_db_error() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    ctx = AsyncMock()
    ctx.__aenter__.side_effect = SQLAlchemyError("connection refused")
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _set_trip_status("trip-1", "generating")  # must not raise


# ── _persist_pending_approvals ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_pending_approvals_inserts_new() -> None:
    session, ctx = _make_session_mock()
    session.get.return_value = None  # approval not in DB yet
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _persist_pending_approvals("trip-1", [_pending_approval("a-new")])
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_pending_approvals_skips_existing() -> None:
    session, ctx = _make_session_mock()
    session.get.return_value = MagicMock()  # already in DB
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _persist_pending_approvals("trip-1", [_pending_approval("a-exists")])
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_pending_approvals_skips_item_without_id() -> None:
    session, ctx = _make_session_mock()
    session.get.return_value = None
    no_id = {
        "proposed_by": "x",
        "change_type": "x",
        "summary": "",
        "payload": {},
        "status": "pending",
    }
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _persist_pending_approvals("trip-1", [no_id])
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_pending_approvals_inserts_correct_record() -> None:
    from backend.db.models import Approval

    session, ctx = _make_session_mock()
    session.get.return_value = None
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _persist_pending_approvals("trip-X", [_pending_approval("appr-check")])
    record = session.add.call_args[0][0]
    assert isinstance(record, Approval)
    assert record.id == "appr-check"
    assert record.trip_id == "trip-X"
    assert record.status == "pending"


@pytest.mark.asyncio
async def test_persist_pending_approvals_handles_db_error() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    ctx = AsyncMock()
    ctx.__aenter__.side_effect = SQLAlchemyError("timeout")
    with patch("backend.workflows.celery_tasks.AsyncSessionLocal", return_value=ctx):
        await _persist_pending_approvals("trip-1", [_pending_approval()])  # must not raise


# ── _run_trip_graph — happy path (no approvals) ───────────────────────────────


@pytest.mark.asyncio
async def test_run_trip_graph_returns_planned_on_clean_run() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([]))
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
    ):
        result = await _run_trip_graph("trip-1", "user-1")
    assert result["status"] == "planned"
    assert result["trip_id"] == "trip-1"


@pytest.mark.asyncio
async def test_run_trip_graph_result_contains_thread_id() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([]))
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
    ):
        result = await _run_trip_graph("trip-1", "user-1")
    assert "thread_id" in result
    assert isinstance(result["thread_id"], str)


@pytest.mark.asyncio
async def test_run_trip_graph_two_ainvoke_calls_on_clean_run() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([]))
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
    ):
        await _run_trip_graph("trip-1", "user-1")
    assert graph.ainvoke.call_count == 2  # Phase 1 + Phase 2


@pytest.mark.asyncio
async def test_run_trip_graph_first_ainvoke_passes_initial_state() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([]))
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
    ):
        await _run_trip_graph("trip-abc", "user-abc")
    first_call_args = graph.ainvoke.call_args_list[0][0]
    state = first_call_args[0]
    assert state["trip_id"] == "trip-abc"
    assert state["user_id"] == "user-abc"


@pytest.mark.asyncio
async def test_run_trip_graph_second_ainvoke_passes_none() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([]))
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
    ):
        await _run_trip_graph("trip-1", "user-1")
    second_call_args = graph.ainvoke.call_args_list[1][0]
    assert second_call_args[0] is None


@pytest.mark.asyncio
async def test_run_trip_graph_sets_generating_first() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([]))
    mock_set_status = AsyncMock()
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", mock_set_status),
    ):
        await _run_trip_graph("trip-1", "user-1")
    first_call = mock_set_status.call_args_list[0]
    assert first_call[0][1] == "generating"


# ── _run_trip_graph — awaiting_approval path ──────────────────────────────────


@pytest.mark.asyncio
async def test_run_trip_graph_returns_awaiting_when_pending_approvals() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([_pending_approval()]))
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
        patch("backend.workflows.celery_tasks._persist_pending_approvals", new_callable=AsyncMock),
    ):
        result = await _run_trip_graph("trip-1", "user-1")
    assert result["status"] == "awaiting_approval"
    assert result["pending_approvals"] == 1


@pytest.mark.asyncio
async def test_run_trip_graph_one_ainvoke_call_when_approvals_pending() -> None:
    graph = _make_graph_mock(snapshot=_make_snapshot([_pending_approval()]))
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
        patch("backend.workflows.celery_tasks._persist_pending_approvals", new_callable=AsyncMock),
    ):
        await _run_trip_graph("trip-1", "user-1")
    assert graph.ainvoke.call_count == 1  # Phase 1 only — no resume


@pytest.mark.asyncio
async def test_run_trip_graph_calls_persist_with_pending_list() -> None:
    pending = [_pending_approval("a1"), _pending_approval("a2")]
    graph = _make_graph_mock(snapshot=_make_snapshot(pending))
    mock_persist = AsyncMock()
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
        patch("backend.workflows.celery_tasks._persist_pending_approvals", mock_persist),
    ):
        await _run_trip_graph("trip-1", "user-1")
    mock_persist.assert_awaited_once_with("trip-1", pending)


# ── _run_trip_graph — error handling ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_trip_graph_sets_failed_on_graph_exception() -> None:
    graph = AsyncMock()
    graph.ainvoke.side_effect = RuntimeError("graph crashed")
    mock_set_status = AsyncMock()
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", mock_set_status),
        pytest.raises(RuntimeError),
    ):
        await _run_trip_graph("trip-1", "user-1")
    last_call = mock_set_status.call_args_list[-1]
    assert last_call[0][1] == "failed"


@pytest.mark.asyncio
async def test_run_trip_graph_reraises_exception_after_setting_failed() -> None:
    graph = AsyncMock()
    graph.ainvoke.side_effect = ValueError("unexpected")
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
        pytest.raises(ValueError),
    ):
        await _run_trip_graph("trip-1", "user-1")


@pytest.mark.asyncio
async def test_run_trip_graph_snapshot_values_none_treated_as_empty_queue() -> None:
    graph = _make_graph_mock()
    graph.aget_state.return_value = MagicMock(values=None)
    with (
        patch("backend.workflows.celery_tasks.build_trip_graph", return_value=graph),
        patch("backend.workflows.celery_tasks._set_trip_status", new_callable=AsyncMock),
    ):
        result = await _run_trip_graph("trip-1", "user-1")
    # None values → empty queue → no approvals → planned
    assert result["status"] == "planned"
