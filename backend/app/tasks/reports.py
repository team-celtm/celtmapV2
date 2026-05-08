from __future__ import annotations

import asyncio
from typing import Any

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.domain_event_service import DomainEventService
from app.services.report_service import ReportService
from app.services.skill_service import SkillService
from app.tasks.celery_app import celery_app
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure
from app.tasks.projections import refresh_dashboard_projection


@celery_app.task(
    bind=True,
    name="app.tasks.generate_user_report",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def generate_user_report(self: Any, user_id: str) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    event_service = DomainEventService(SyncRepository(client))
    skill_service = SkillService(SkillRepository(client), event_service)
    report_service = ReportService(
        ReportRepository(client),
        AssessmentRepository(client),
        InterviewRepository(client),
        skill_service,
    )
    mark_worker_heartbeat()
    try:
        report = asyncio.run(report_service.generate_report(user_id))
        refresh_dashboard_projection.delay(user_id)
        return {"status": "completed", "user_id": user_id, "report_id": report.get("id")}
    except Exception as exc:
        if self.request.retries >= 3:
            asyncio.run(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.generate_user_report",
                    task_id=getattr(self.request, "id", None),
                    entity_type="report",
                    entity_id=user_id,
                    payload={"user_id": user_id},
                    error=exc,
                    retry_count=self.request.retries,
                )
            )
        raise
