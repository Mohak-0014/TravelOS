"""Approval Gate node — persists pending approvals to the approvals table.

The graph pauses BEFORE this node via interrupt_before=["approval_gate"].
When the graph is resumed (after human review), this node:
  1. Upserts each approval_queue entry into the approvals table.
  2. Skips entries already present (idempotent on re-runs).
  3. Degrades gracefully on DB errors — never crashes the graph.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from sqlalchemy.exc import SQLAlchemyError

from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import Approval
from backend.graphs.state import TravelOSState

logger = get_logger(__name__)


async def run(state: TravelOSState) -> dict:  # type: ignore[type-arg]
    trip_id = state.get("trip_id", "unknown")
    approval_queue: list[dict] = list(state.get("approval_queue") or [])  # type: ignore[arg-type]

    logger.info("approval_gate_start", trip_id=trip_id, queue_size=len(approval_queue))

    persisted: list[str] = []
    skipped: list[str] = []

    if approval_queue:
        try:
            async with AsyncSessionLocal() as session:
                for item in approval_queue:
                    item_id: str = str(item.get("id") or "")
                    if not item_id:
                        logger.warning("approval_gate_item_missing_id", trip_id=trip_id)
                        continue
                    existing = await session.get(Approval, item_id)
                    if existing is None:
                        session.add(
                            Approval(
                                id=item_id,
                                trip_id=trip_id,
                                proposed_by=item.get("proposed_by") or "system",
                                change_type=item.get("change_type") or "unknown",
                                summary=item.get("summary") or "",
                                payload=item.get("payload") or {},
                                status=item.get("status") or "pending",
                            )
                        )
                        persisted.append(item_id)
                    else:
                        skipped.append(item_id)
                await session.commit()
        except SQLAlchemyError as exc:
            logger.error("approval_gate_db_error", trip_id=trip_id, error=str(exc))

    n = len(approval_queue)
    if n == 0:
        summary = "No approvals required"
    else:
        parts = [f"{n} approval(s) in queue"]
        if persisted:
            parts.append(f"{len(persisted)} persisted")
        if skipped:
            parts.append(f"{len(skipped)} already in DB")
        summary = ", ".join(parts)

    logger.info(
        "approval_gate_complete",
        trip_id=trip_id,
        total=n,
        persisted=len(persisted),
        skipped=len(skipped),
    )

    return {
        "current_step": "checkpoint_save",
        "agent_messages": [SystemMessage(content=f"Approval Gate [trip={trip_id}]: {summary}.")],
    }
