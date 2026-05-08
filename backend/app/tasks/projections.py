from __future__ import annotations

import asyncio
from typing import Any

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.report_repository import ReportRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.dashboard_service import DashboardService
from app.services.domain_event_service import DomainEventService
from app.services.projection_service import ProjectionService
from app.services.schedule_service import ScheduleService
from app.services.skill_service import SkillService
from app.tasks.celery_app import celery_app
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure


@celery_app.task(
    bind=True,
    name="app.tasks.refresh_dashboard_projection",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def refresh_dashboard_projection(self: Any, user_id: str) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    event_service = DomainEventService(SyncRepository(client))
    skill_service = SkillService(SkillRepository(client), event_service)
    schedule_service = ScheduleService(ScheduleRepository(client))
    dashboard_service = DashboardService(ReportRepository(client), skill_service, schedule_service)
    projection_service = ProjectionService(ReportRepository(client), dashboard_service)
    mark_worker_heartbeat()
    try:
        projection = asyncio.run(projection_service.refresh_dashboard_projection(user_id))
        return {"status": "completed", "user_id": user_id, "projection_id": projection.get("id")}
    except Exception as exc:
        if self.request.retries >= 3:
            asyncio.run(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.refresh_dashboard_projection",
                    task_id=getattr(self.request, "id", None),
                    entity_type="dashboard_projection",
                    entity_id=user_id,
                    payload={"user_id": user_id},
                    error=exc,
                    retry_count=self.request.retries,
                )
            )
        raise
