"""Transactional outbox helper.

Stage a Celery task to dispatch *in the same DB transaction* as the business data that
triggers it, instead of calling ``.delay()`` after commit. The ``drain_outbox`` relay
(see ``celery_tasks``) then forwards pending rows to the broker. This closes the
dual-write gap: if the transaction commits, the task is guaranteed to be dispatched
eventually; if it rolls back, nothing is enqueued.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import OutboxEvent


async def enqueue(session: AsyncSession, task_name: str, payload: dict[str, Any]) -> OutboxEvent:
    """Stage a Celery task for dispatch within the caller's transaction.

    The caller is responsible for committing the session; the outbox row then lands
    atomically with the rest of their changes.
    """
    event = OutboxEvent(task_name=task_name, payload=payload)
    session.add(event)
    return event
