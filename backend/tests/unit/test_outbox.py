"""Unit tests for the transactional outbox: the enqueue helper and the drain relay."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.db.models import OutboxEvent
from backend.workflows.outbox import enqueue


@pytest.mark.asyncio
async def test_enqueue_stages_pending_event(db_session: AsyncSession) -> None:
    event = await enqueue(db_session, "some.task", {"trip_id": "t1"})
    await db_session.commit()

    rows = list((await db_session.execute(select(OutboxEvent))).scalars().all())
    assert len(rows) == 1
    assert rows[0].id == event.id
    assert rows[0].task_name == "some.task"
    assert rows[0].payload == {"trip_id": "t1"}
    assert rows[0].status == "pending"
    assert rows[0].attempts == 0


@pytest.mark.asyncio
async def test_drain_dispatches_pending(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.workflows import celery_tasks

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as s:
        s.add(OutboxEvent(task_name="t.embed", payload={"feedback_id": "f1"}))
        await s.commit()

    sent: list[tuple[str, dict]] = []  # type: ignore[type-arg]
    monkeypatch.setattr(
        celery_tasks.celery_app,
        "send_task",
        lambda name, kwargs=None: sent.append((name, kwargs)),
    )
    monkeypatch.setattr(celery_tasks, "AsyncSessionLocal", maker)

    result = await celery_tasks._drain_outbox()

    assert result == {"dispatched": 1, "scanned": 1}
    assert sent == [("t.embed", {"feedback_id": "f1"})]
    async with maker() as s:
        ev = (await s.execute(select(OutboxEvent))).scalar_one()
        assert ev.status == "dispatched"
        assert ev.dispatched_at is not None


@pytest.mark.asyncio
async def test_drain_marks_failed_after_repeated_send_errors(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.workflows import celery_tasks

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as s:
        # attempts=4 → one more failure crosses the threshold of 5 and marks it failed.
        s.add(OutboxEvent(task_name="t.bad", payload={}, attempts=4))
        await s.commit()

    def _boom(name: str, kwargs: dict | None = None) -> None:  # type: ignore[type-arg]
        raise RuntimeError("broker down")

    monkeypatch.setattr(celery_tasks.celery_app, "send_task", _boom)
    monkeypatch.setattr(celery_tasks, "AsyncSessionLocal", maker)

    result = await celery_tasks._drain_outbox()

    assert result == {"dispatched": 0, "scanned": 1}
    async with maker() as s:
        ev = (await s.execute(select(OutboxEvent))).scalar_one()
        assert ev.status == "failed"
        assert ev.attempts == 5
        assert "broker down" in (ev.last_error or "")
