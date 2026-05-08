from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.models.enums import DomainEventType
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.domain_event_service import DomainEventService
from app.services.skill_service import SkillService
from app.tasks.artifacts import extract_uploaded_artifact
from app.tasks.celery_app import celery_app
from app.tasks.graph import sync_user_graph
from app.tasks.interviews import evaluate_interview_session
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure
from app.tasks.projections import refresh_dashboard_projection
from app.tasks.reports import generate_user_report


def _skill_id(skill_name: str) -> str:
    return skill_name.strip().lower().replace(" ", "_")


@celery_app.task(name="app.tasks.process_retryable_domain_events")
def process_retryable_domain_events(limit: int = 100) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    repository = SyncRepository(client)
    mark_worker_heartbeat()
    events = asyncio.run(repository.list_retryable_events(limit=limit, max_retry_count=3))
    queued = []
    for event in events:
        process_domain_event.delay(event["id"])
        queued.append(event["id"])
    return {"queued": queued, "count": len(queued)}


@celery_app.task(
    bind=True,
    name="app.tasks.process_domain_event",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def process_domain_event(self: Any, event_id: str) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    repository = SyncRepository(client)
    event = asyncio.run(repository.get_event(event_id))
    if event is None:
        return {"status": "missing", "event_id": event_id}
    if event.get("status") == "completed":
        return {"status": "skipped", "event_id": event_id}

    asyncio.run(
        repository.update_event(
            event_id,
            {
                "status": "processing",
                "processing_started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )

    mark_worker_heartbeat()
    try:
        result = _dispatch_event(event)
        asyncio.run(
            repository.update_event(
                event_id,
                {
                    "status": "completed",
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "last_error": None,
                },
            )
        )
        return {"status": "completed", "event_id": event_id, "result": result}
    except Exception as exc:
        retry_count = int(event.get("retry_count") or 0) + 1
        asyncio.run(
            repository.update_event(
                event_id,
                {
                    "status": "failed",
                    "retry_count": retry_count,
                    "last_error": str(exc),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
        if self.request.retries >= 3:
            asyncio.run(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.process_domain_event",
                    task_id=getattr(self.request, "id", None),
                    entity_type="domain_event",
                    entity_id=event_id,
                    payload={"event_id": event_id, "event_type": event.get("event_type")},
                    error=exc,
                    retry_count=retry_count,
                )
            )
        raise


def _dispatch_event(event: dict) -> dict:
    event_type = event["event_type"]
    payload = event.get("payload") or {}
    user_id = payload.get("user_id")

    if event_type == DomainEventType.ASSESSMENT_COMPLETED.value:
        asyncio.run(_apply_assessment_score(payload))
        if user_id:
            refresh_dashboard_projection.delay(user_id)
            generate_user_report.delay(user_id)
            sync_user_graph.delay(user_id, event["id"])
        return {"handled_as": "assessment"}

    if event_type == DomainEventType.INTERVIEW_COMPLETED.value:
        evaluate_interview_session.delay(event["aggregate_id"], user_id, event["id"])
        return {"handled_as": "interview"}

    if event_type == DomainEventType.HIDDEN_SKILL_APPROVED.value:
        if user_id:
            refresh_dashboard_projection.delay(user_id)
            generate_user_report.delay(user_id)
            sync_user_graph.delay(user_id, event["id"])
        return {"handled_as": "hidden_skill"}

    if event_type == DomainEventType.ARTIFACT_UPLOADED.value:
        artifact_id = payload.get("artifact_id")
        if artifact_id:
            extract_uploaded_artifact.delay(artifact_id)
        return {"handled_as": "artifact"}

    if event_type == DomainEventType.SKILL_MEASURED.value:
        if user_id:
            refresh_dashboard_projection.delay(user_id)
            generate_user_report.delay(user_id)
        return {"handled_as": "skill_measured"}

    return {"handled_as": "noop"}


async def _apply_assessment_score(payload: dict) -> None:
    user_id = payload.get("user_id")
    category = payload.get("category")
    score = payload.get("score")
    if not user_id or category is None or score is None:
        return

    settings = get_settings()
    client = get_supabase_client(settings)
    skill_repository = SkillRepository(client)
    event_service = DomainEventService(SyncRepository(client))
    skill_service = SkillService(skill_repository, event_service)
    existing_skills = await skill_repository.list_user_skills(user_id)
    existing = next((item for item in existing_skills if item["skill_name"] == category), {})
    proficiency_score = skill_service.compute_weighted_skill_score(
        assessment_score=float(score),
        written_score=existing.get("written_score"),
        interview_score=existing.get("interview_score"),
        artifact_score=existing.get("artifact_score"),
    )
    await skill_repository.upsert_user_skill(
        {
            "user_id": user_id,
            "skill_id": existing.get("skill_id") or _skill_id(category),
            "skill_name": category,
            "proficiency_score": proficiency_score,
            "assessment_score": float(score),
            "written_score": existing.get("written_score"),
            "interview_score": existing.get("interview_score"),
            "artifact_score": existing.get("artifact_score"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
