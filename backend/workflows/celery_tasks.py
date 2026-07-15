import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

from celery import Celery
from celery.schedules import crontab
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import AsyncSessionLocal
from backend.db.models import (
    Approval,
    ItineraryItem,
    OutboxEvent,
    Preference,
    Trip,
    UserFeedback,
)
from backend.graphs.replan_graph import build_replan_graph
from backend.graphs.state import TravelOSState
from backend.graphs.trip_graph import build_trip_graph
from backend.memory.embeddings import embed_text, feedback_text, preference_text, trip_memory_text
from backend.memory.semantic import (
    ensure_collections,
    get_qdrant_client,
    upsert_feedback,
    upsert_preferences,
    upsert_trip_memory,
)

logger = get_logger(__name__)

celery_app = Celery(
    "travelos",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Prevent runaway tasks from blocking workers
    task_time_limit=600,
    task_soft_time_limit=540,
    beat_schedule={
        "check-weather-every-6h": {
            "task": "backend.workflows.celery_tasks.check_weather_and_replan_all",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # Transactional-outbox relay: forward staged tasks to the broker.
        "drain-outbox-every-10s": {
            "task": "backend.workflows.celery_tasks.drain_outbox",
            "schedule": 10.0,
        },
    },
)


# ── Itinerary generation ───────────────────────────────────────────────────────


@celery_app.task(name="backend.workflows.celery_tasks.generate_itinerary_async", bind=True)
def generate_itinerary_async(self, trip_id: str, user_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Entry point for AI itinerary generation.
    Runs the full trip_graph via asyncio.run() inside the Celery prefork worker.

    Two-phase execution:
      Phase 1: Run supervisor → … → conflict_detection (graph pauses at interrupt).
      Phase 2: If no pending approvals, resume through approval_gate → checkpoint_save.
               If pending approvals, persist them and leave trip as awaiting_approval.
    """
    from backend.db.base import engine

    # asyncpg connections are bound to the event loop that created them.
    # asyncio.run() creates a fresh event loop each call, so we must dispose
    # the pool first to avoid "another operation is in progress" errors.
    engine.sync_engine.dispose()

    logger.info("generate_itinerary_async_received", trip_id=trip_id, user_id=user_id)
    try:
        return asyncio.run(_run_trip_graph(trip_id, user_id))
    except Exception as exc:
        logger.error("generate_itinerary_async_failed", trip_id=trip_id, error=str(exc))
        engine.sync_engine.dispose()
        asyncio.run(_set_trip_status(trip_id, "failed"))
        raise self.retry(exc=exc, countdown=30, max_retries=2) from exc


# ── Async helpers (called via asyncio.run inside the sync Celery task) ─────────


async def _run_trip_graph(trip_id: str, user_id: str) -> dict:  # type: ignore[return]
    """
    Core async logic for itinerary generation.
    Separated from the Celery task so it can be unit-tested directly.
    """
    thread_id = str(uuid.uuid4())
    checkpointer = MemorySaver()
    graph = build_trip_graph(checkpointer=checkpointer)
    config: dict = {"configurable": {"thread_id": thread_id}}  # type: ignore[type-arg]

    initial_state: TravelOSState = {
        "trip_id": trip_id,
        "user_id": user_id,
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {"risk_flags": [], "last_checked": None, "forecast": []},
        "budget_state": {"total": None, "spent": 0.0, "by_category": {}, "breach_pct": 0.0},
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "start",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }

    # Mark trip as generating and clear any stale pending approvals from previous
    # generations — they reference old itinerary item IDs and wrong cost data.
    await _set_trip_status(trip_id, "generating", thread_id=thread_id)
    await _clear_pending_approvals(trip_id)

    try:
        # Phase 1: run until interrupt_before=["approval_gate"]
        await graph.ainvoke(initial_state, config)

        # Inspect state at the interrupt point
        snapshot = await graph.aget_state(config)
        approval_queue: list[dict] = list(  # type: ignore[type-arg]
            (snapshot.values or {}).get("approval_queue") or []
        )
        pending = [a for a in approval_queue if a.get("status") == "pending"]

        if pending:
            # Approvals needed — persist to DB and leave graph paused
            await _persist_pending_approvals(trip_id, pending)
            await _set_trip_status(trip_id, "awaiting_approval")
            logger.info(
                "generate_itinerary_awaiting_approval",
                trip_id=trip_id,
                approvals=len(pending),
                thread_id=thread_id,
            )
            return {
                "status": "awaiting_approval",
                "trip_id": trip_id,
                "thread_id": thread_id,
                "pending_approvals": len(pending),
            }

        # Phase 2: no approvals — resume through approval_gate → checkpoint_save → END
        # checkpoint_save_node updates trip status and langgraph_thread_id in DB
        await graph.ainvoke(None, config)

        logger.info("generate_itinerary_completed", trip_id=trip_id, thread_id=thread_id)
        return {"status": "planned", "trip_id": trip_id, "thread_id": thread_id}

    except Exception:
        await _set_trip_status(trip_id, "failed")
        raise


async def _clear_pending_approvals(trip_id: str) -> None:
    """Delete all pending approvals for a trip before a new generation run."""
    from sqlalchemy import delete as sa_delete  # noqa: PLC0415

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                sa_delete(Approval).where(
                    Approval.trip_id == trip_id,
                    Approval.status == "pending",
                )
            )
            await session.commit()
    except SQLAlchemyError as exc:
        logger.warning("clear_pending_approvals_error", trip_id=trip_id, error=str(exc))


async def _set_trip_status(
    trip_id: str,
    status: str,
    thread_id: str | None = None,
) -> None:
    """Update trips.status and optionally langgraph_thread_id."""
    try:
        async with AsyncSessionLocal() as session:
            trip = await session.get(Trip, trip_id)
            if trip is not None:
                trip.status = status
                if thread_id:
                    trip.langgraph_thread_id = thread_id
                await session.commit()
            else:
                logger.warning("set_trip_status_not_found", trip_id=trip_id)
    except SQLAlchemyError as exc:
        logger.error("set_trip_status_db_error", trip_id=trip_id, error=str(exc))


async def _persist_pending_approvals(
    trip_id: str,
    approvals: list[dict],  # type: ignore[type-arg]
) -> None:
    """Persist approval_queue items to the approvals table when graph stays paused."""
    try:
        async with AsyncSessionLocal() as session:
            for item in approvals:
                item_id = str(item.get("id") or "")
                if not item_id:
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
                            status="pending",
                        )
                    )
            await session.commit()
    except SQLAlchemyError as exc:
        logger.error("persist_approvals_db_error", trip_id=trip_id, error=str(exc))


async def _run_replan_graph(trip_id: str) -> dict:  # type: ignore[return]
    """Run the weather replan graph for a single trip."""
    async with AsyncSessionLocal() as session:
        trip = await session.get(Trip, trip_id)
        if trip is None:
            logger.warning("replan_trip_not_found", trip_id=trip_id)
            return {"status": "skipped", "reason": "trip not found", "trip_id": trip_id}
        user_id = str(trip.user_id)

    thread_id = str(uuid.uuid4())
    checkpointer = MemorySaver()
    graph = build_replan_graph(checkpointer=checkpointer)
    config: dict = {"configurable": {"thread_id": thread_id}}  # type: ignore[type-arg]

    initial_state: TravelOSState = {
        "trip_id": trip_id,
        "user_id": user_id,
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {
            "risk_flags": [],
            "last_checked": None,
            "forecast": [],
            "affected_items": [],
        },
        "budget_state": {"total": None, "spent": 0.0, "by_category": {}, "breach_pct": 0.0},
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "start",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }

    await graph.ainvoke(initial_state, config)
    logger.info("replan_graph_completed", trip_id=trip_id, thread_id=thread_id)
    return {"status": "completed", "trip_id": trip_id, "thread_id": thread_id}


async def _find_active_trips() -> list[str]:
    """Return trip IDs for planned trips starting within the next 7 days."""
    today = date.today()
    cutoff = today + timedelta(days=7)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Trip.id).where(
                    Trip.status == "planned",
                    Trip.start_date >= today,
                    Trip.start_date <= cutoff,
                )
            )
            return [str(row[0]) for row in result.all()]
    except SQLAlchemyError as exc:
        logger.error("find_active_trips_error", error=str(exc))
        return []


# ── Weather replanning ─────────────────────────────────────────────────────────


@celery_app.task(name="backend.workflows.celery_tasks.check_weather_and_replan_all")
def check_weather_and_replan_all() -> dict:  # type: ignore[no-untyped-def]
    """
    Scheduled by Celery Beat every 6 hours.
    Finds all planned trips starting within 7 days and fans out per-trip tasks.
    """
    logger.info("check_weather_and_replan_all_start")
    try:
        trip_ids = asyncio.run(_find_active_trips())
    except Exception as exc:
        logger.error("check_weather_and_replan_all_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}

    for trip_id in trip_ids:
        check_weather_and_replan.delay(trip_id)

    logger.info("check_weather_and_replan_all_dispatched", count=len(trip_ids))
    return {"status": "dispatched", "count": len(trip_ids)}


@celery_app.task(name="backend.workflows.celery_tasks.check_weather_and_replan", bind=True)
def check_weather_and_replan(self, trip_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Fetch fresh weather for a single trip and invoke the replan graph.
    Creates approval records for any outdoor items on adverse-weather days.
    """
    from backend.db.base import engine

    engine.sync_engine.dispose()
    logger.info("check_weather_and_replan_received", trip_id=trip_id)
    try:
        return asyncio.run(_run_replan_graph(trip_id))
    except Exception as exc:
        logger.error("check_weather_and_replan_failed", trip_id=trip_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=2) from exc


# ── Embedding tasks (always run in Celery — NEVER in request path) ─────────────


@celery_app.task(name="backend.workflows.celery_tasks.embed_preferences_async")
def embed_preferences_async(user_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Generate and upsert preference embeddings for a user into Qdrant.
    Triggered whenever a user saves/updates their preferences.
    """
    from backend.db.base import engine

    engine.sync_engine.dispose()
    logger.info("embed_preferences_async_received", user_id=user_id)
    try:
        return asyncio.run(_run_embed_preferences(user_id))
    except Exception as exc:
        logger.error("embed_preferences_async_failed", user_id=user_id, error=str(exc))
        return {"status": "error", "user_id": user_id, "error": str(exc)}


@celery_app.task(name="backend.workflows.celery_tasks.embed_trip_summary_async")
def embed_trip_summary_async(trip_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Summarise and embed a completed trip into Qdrant trip_memories collection.
    Triggered after a trip reaches 'planned' status.
    """
    from backend.db.base import engine

    engine.sync_engine.dispose()
    logger.info("embed_trip_summary_async_received", trip_id=trip_id)
    try:
        return asyncio.run(_run_embed_trip(trip_id))
    except Exception as exc:
        logger.error("embed_trip_summary_async_failed", trip_id=trip_id, error=str(exc))
        return {"status": "error", "trip_id": trip_id, "error": str(exc)}


async def _run_embed_preferences(user_id: str) -> dict:  # type: ignore[return]
    """Load preferences from DB, embed, and upsert into Qdrant."""
    async with AsyncSessionLocal() as session:
        pref_result = await session.execute(select(Preference).where(Preference.user_id == user_id))
        pref = pref_result.scalar_one_or_none()

    if pref is None:
        logger.warning("embed_preferences_no_pref_found", user_id=user_id)
        return {"status": "skipped", "reason": "no preferences found", "user_id": user_id}

    prefs_dict = {
        "pace": pref.pace,
        "luxury_tier": pref.luxury_tier,
        "walking_tolerance": pref.walking_tolerance,
        "interests": list(pref.interests or []),
        "food_prefs": list(pref.food_prefs or []),
        "budget_behavior": pref.budget_behavior,
    }

    text = preference_text(prefs_dict)
    vector = embed_text(text)

    client = get_qdrant_client()
    try:
        await ensure_collections(client)
        await upsert_preferences(client, user_id, vector, {"text_summary": text, **prefs_dict})
    finally:
        await client.close()

    logger.info("embed_preferences_complete", user_id=user_id)
    return {"status": "ok", "user_id": user_id}


async def _run_embed_trip(trip_id: str) -> dict:  # type: ignore[return]
    """Load trip + itinerary from DB, embed a summary, and upsert into Qdrant."""
    async with AsyncSessionLocal() as session:
        trip = await session.get(Trip, trip_id)
        if trip is None:
            logger.warning("embed_trip_not_found", trip_id=trip_id)
            return {"status": "skipped", "reason": "trip not found", "trip_id": trip_id}

        items_result = await session.execute(
            select(ItineraryItem)
            .where(ItineraryItem.trip_id == trip_id)
            .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
        )
        items = items_result.scalars().all()

    style_tags: list[str] = []
    item_titles = [i.title for i in items if i.item_type == "activity"]

    text = trip_memory_text(
        city=trip.destination_city,
        country=trip.destination_country,
        style_tags=style_tags,
        item_titles=item_titles,
    )
    vector = embed_text(text)

    payload = {
        "destination_city": trip.destination_city,
        "destination_country": trip.destination_country,
        "start_date": trip.start_date.isoformat(),
        "end_date": trip.end_date.isoformat(),
        "num_travelers": trip.num_travelers,
        "text_summary": text,
    }

    client = get_qdrant_client()
    try:
        await ensure_collections(client)
        await upsert_trip_memory(client, trip_id, str(trip.user_id), vector, payload)
    finally:
        await client.close()

    logger.info("embed_trip_complete", trip_id=trip_id)
    return {"status": "ok", "trip_id": trip_id}


@celery_app.task(name="backend.workflows.celery_tasks.embed_feedback_async")
def embed_feedback_async(feedback_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Embed a UserFeedback record and upsert into the Qdrant user_feedback collection.
    Triggered after every approve/reject decision in the approvals router.
    """
    from backend.db.base import engine

    engine.sync_engine.dispose()
    logger.info("embed_feedback_async_received", feedback_id=feedback_id)
    try:
        return asyncio.run(_run_embed_feedback(feedback_id))
    except Exception as exc:
        logger.error("embed_feedback_async_failed", feedback_id=feedback_id, error=str(exc))
        return {"status": "error", "feedback_id": feedback_id, "error": str(exc)}


async def _run_embed_feedback(feedback_id: str) -> dict:  # type: ignore[return]
    """Load UserFeedback from DB, embed, and upsert into Qdrant."""
    async with AsyncSessionLocal() as session:
        fb = await session.get(UserFeedback, feedback_id)
        if fb is None:
            logger.warning("embed_feedback_not_found", feedback_id=feedback_id)
            return {"status": "skipped", "reason": "not found", "feedback_id": feedback_id}

        _decision = str(fb.decision or "")
        _change_type = str(fb.change_type or "")
        _context_tags: list[str] = [str(t) for t in (fb.context_tags or [])]
        _summary = str(fb.summary or "")
        fb_dict: dict[str, object] = {
            "decision": _decision,
            "change_type": _change_type,
            "context_tags": _context_tags,
            "summary": _summary,
        }

    text = feedback_text(
        decision=_decision,
        change_type=_change_type,
        context_tags=_context_tags,
        summary=_summary,
    )
    vector = embed_text(text)

    payload = {
        "feedback_id": feedback_id,
        "decision": fb_dict["decision"],
        "change_type": fb_dict["change_type"],
        "context_tags": fb_dict["context_tags"],
        "summary": fb_dict["summary"],
    }

    client = get_qdrant_client()
    try:
        await ensure_collections(client)
        await upsert_feedback(client, str(fb.approval_id), str(fb.user_id), vector, payload)
    finally:
        await client.close()

    logger.info("embed_feedback_complete", feedback_id=feedback_id)
    return {"status": "ok", "feedback_id": feedback_id}


# ── Transactional outbox relay ─────────────────────────────────────────────────


@celery_app.task(name="backend.workflows.celery_tasks.drain_outbox")
def drain_outbox() -> dict:  # type: ignore[no-untyped-def]
    """Forward staged outbox rows to the broker. Scheduled by Celery Beat every 10s."""
    from backend.db.base import engine

    # Purge pool entries left by tasks that ran on earlier (now-closed) event
    # loops, so the checkout below never reuses a loop-dead connection.
    engine.sync_engine.dispose()
    return asyncio.run(_drain_outbox())


async def _drain_outbox(batch_size: int = 100) -> dict[str, int]:
    """Dispatch pending OutboxEvent rows to Celery, marking each dispatched or failed."""
    from backend.db.base import engine

    dispatched = 0
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending")
                .order_by(OutboxEvent.created_at)
                .limit(batch_size)
            )
            events = list(result.scalars().all())
            for event in events:
                try:
                    celery_app.send_task(event.task_name, kwargs=event.payload or {})
                    event.status = "dispatched"
                    event.dispatched_at = datetime.now(UTC)
                    dispatched += 1
                except Exception as exc:
                    event.attempts += 1
                    event.last_error = str(exc)[:500]
                    if event.attempts >= 5:
                        event.status = "failed"
                    logger.error("outbox_dispatch_failed", event_id=str(event.id), error=str(exc))
            await session.commit()
    finally:
        # Close this run's connections while their event loop is still alive.
        # asyncio.run() destroys the loop on return, after which a pooled
        # asyncpg connection can never be awaited closed — it would leak
        # server-side (one per beat tick) until Postgres hits max_connections.
        await engine.dispose()

    logger.info("outbox_drained", dispatched=dispatched, scanned=len(events))
    return {"dispatched": dispatched, "scanned": len(events)}
