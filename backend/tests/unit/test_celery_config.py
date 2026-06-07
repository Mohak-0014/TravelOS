from backend.core.config import settings
from backend.workflows.celery_tasks import celery_app


def test_broker_url_matches_settings() -> None:
    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL


def test_result_backend_matches_settings() -> None:
    assert celery_app.conf.result_backend == settings.CELERY_RESULT_BACKEND


def test_all_tasks_registered() -> None:
    registered = set(celery_app.tasks.keys())
    expected = {
        "backend.workflows.celery_tasks.generate_itinerary_async",
        "backend.workflows.celery_tasks.check_weather_and_replan_all",
        "backend.workflows.celery_tasks.check_weather_and_replan",
        "backend.workflows.celery_tasks.embed_preferences_async",
        "backend.workflows.celery_tasks.embed_trip_summary_async",
    }
    assert expected.issubset(registered)


def test_beat_schedule_has_weather_task() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "check-weather-every-6h" in schedule
    task_name = schedule["check-weather-every-6h"]["task"]
    assert task_name == "backend.workflows.celery_tasks.check_weather_and_replan_all"


def test_task_time_limits_set() -> None:
    assert celery_app.conf.task_time_limit == 600
    assert celery_app.conf.task_soft_time_limit == 540


def test_task_serializer_is_json() -> None:
    assert celery_app.conf.task_serializer == "json"
