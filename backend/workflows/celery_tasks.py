from celery import Celery
from celery.schedules import crontab

from backend.core.config import settings
from backend.core.logging import get_logger

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
    # Route embedding tasks to low-priority queue, generation to high-priority
    task_routes={
        "backend.workflows.celery_tasks.embed_preferences_async": {"queue": "low"},
        "backend.workflows.celery_tasks.embed_trip_summary_async": {"queue": "low"},
        "backend.workflows.celery_tasks.generate_itinerary_async": {"queue": "high"},
        "backend.workflows.celery_tasks.check_weather_and_replan": {"queue": "high"},
    },
    beat_schedule={
        "check-weather-every-6h": {
            "task": "backend.workflows.celery_tasks.check_weather_and_replan_all",
            "schedule": crontab(minute=0, hour="*/6"),
        },
    },
)


# ── Itinerary generation ───────────────────────────────────────────────────────

@celery_app.task(name="backend.workflows.celery_tasks.generate_itinerary_async", bind=True)
def generate_itinerary_async(self, trip_id: str, user_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Entry point for AI itinerary generation. Runs the full trip_graph.
    Stub — fully wired in Week 7 when itinerary_planner agent is ready.
    """
    logger.info("generate_itinerary_async_received", trip_id=trip_id, user_id=user_id)
    return {"status": "queued", "trip_id": trip_id}


# ── Weather replanning ─────────────────────────────────────────────────────────

@celery_app.task(name="backend.workflows.celery_tasks.check_weather_and_replan_all")
def check_weather_and_replan_all() -> dict:  # type: ignore[no-untyped-def]
    """
    Scheduled by Celery Beat every 6 hours.
    Finds all active trips starting within 7 days and fans out individual tasks.
    Stub — fully implemented in Week 15.
    """
    logger.info("check_weather_and_replan_all_stub")
    return {"status": "stub"}


@celery_app.task(name="backend.workflows.celery_tasks.check_weather_and_replan", bind=True)
def check_weather_and_replan(self, trip_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Fetch fresh weather for a single trip and invoke the replan graph if adverse.
    Stub — fully implemented in Week 15.
    """
    logger.info("check_weather_and_replan_stub", trip_id=trip_id)
    return {"status": "stub", "trip_id": trip_id}


# ── Embedding tasks (always run in Celery — NEVER in request path) ─────────────

@celery_app.task(name="backend.workflows.celery_tasks.embed_preferences_async")
def embed_preferences_async(user_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Generate and upsert preference embeddings for a user into Qdrant.
    Stub — fully implemented in Week 11.
    """
    logger.info("embed_preferences_async_stub", user_id=user_id)
    return {"status": "stub", "user_id": user_id}


@celery_app.task(name="backend.workflows.celery_tasks.embed_trip_summary_async")
def embed_trip_summary_async(trip_id: str) -> dict:  # type: ignore[no-untyped-def]
    """
    Summarise and embed a completed trip into Qdrant trip_memories collection.
    Stub — fully implemented in Week 12.
    """
    logger.info("embed_trip_summary_async_stub", trip_id=trip_id)
    return {"status": "stub", "trip_id": trip_id}
