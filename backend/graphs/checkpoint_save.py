"""Checkpoint Save node — finalises the trip record after the graph completes.

Responsibilities:
  - Update trips.status to "planned" (no pending approvals) or
    "awaiting_approval" (one or more approvals still pending).
  - Write the LangGraph thread_id into trips.langgraph_thread_id so the
    Celery task / API can resume the graph later.
  - Write the thread_id into state["run_checkpoint_ref"] for downstream use.
  - Degrades gracefully on DB errors — never crashes the graph.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import Approval, Trip
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)


async def run(
    state: TravelOSState,
    config: RunnableConfig | None = None,
) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")

    # Extract thread_id from the LangGraph config passed by the runtime
    configurable: dict = (config or {}).get("configurable") or {}  # type: ignore[assignment]
    thread_id: str | None = configurable.get("thread_id")

    new_status = "planned"  # default if DB query fails

    try:
        async with AsyncSessionLocal() as session:
            # Query DB for pending approvals — includes direct-write agents (budget, concierge)
            pending_result = await session.execute(
                select(Approval).where(
                    Approval.trip_id == trip_id,
                    Approval.status == "pending",
                )
            )
            has_pending = pending_result.scalars().first() is not None
            new_status = "awaiting_approval" if has_pending else "planned"

            trip = await session.get(Trip, trip_id)
            if trip is not None:
                trip.status = new_status
                if thread_id:
                    trip.langgraph_thread_id = thread_id
                await session.commit()
            else:
                logger.warning("checkpoint_save_trip_not_found", trip_id=trip_id)
    except SQLAlchemyError as exc:
        logger.error("checkpoint_save_db_error", trip_id=trip_id, error=str(exc))

    logger.info(
        "checkpoint_save_complete",
        trip_id=trip_id,
        status=new_status,
        thread_id=thread_id,
    )

    msg_parts = [f"status={new_status}"]
    if thread_id:
        msg_parts.append(f"thread_id={thread_id}")

    return {
        "current_step": "end",
        "run_checkpoint_ref": thread_id,
        "agent_messages": [
            SystemMessage(content=f"Checkpoint Save [trip={trip_id}]: {', '.join(msg_parts)}.")
        ],
    }
