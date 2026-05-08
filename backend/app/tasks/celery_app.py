from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config.settings import get_settings

settings = get_settings()
beat_schedule = {
    "process-domain-events": {
        "task": "app.tasks.process_retryable_domain_events",
        "schedule": crontab(minute="*/5"),
    },
}

if settings.can_sync_celtmind:
    beat_schedule["sync-celtmind"] = {
        "task": "app.tasks.run_celtmind_sync",
        "schedule": crontab(minute="*/30"),
    }

celery_app = Celery(
    "celtm_backend",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=[
        "app.tasks.artifacts",
        "app.tasks.domain_events",
        "app.tasks.graph",
        "app.tasks.interviews",
        "app.tasks.projections",
        "app.tasks.reports",
        "app.tasks.sync",
        "app.tasks.written_assessments",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule=beat_schedule,
    task_always_eager=settings.celery_eager_mode,
    # Do NOT propagate task exceptions back to the caller in eager/dev mode.
    # With task_always_eager=True and task_eager_propagates=True, any exception
    # inside a .delay() call would crash the HTTP request synchronously.
    # In production (eager=False) this setting has no effect.
    task_eager_propagates=False,
)
