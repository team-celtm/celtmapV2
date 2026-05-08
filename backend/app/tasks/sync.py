from __future__ import annotations

import asyncio
from typing import Any

from app.config.settings import get_settings
from app.integrations.cache import CacheClient
from app.integrations.llm import OpenAIProvider
from app.integrations.supabase import get_supabase_client
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.ops_repository import OpsRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.rag_repository import RagRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.celtmind_sync import CeltmindSyncService
from app.services.domain_event_service import DomainEventService
from app.services.ops_service import OpsService
from app.services.rag_service import RagService
from app.tasks.celery_app import celery_app
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure


@celery_app.task(
    bind=True,
    name="app.tasks.run_celtmind_sync",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_celtmind_sync(self: Any) -> dict:
    settings = get_settings()
    if not settings.can_sync_celtmind:
        return {
            "status": "skipped",
            "reason": "CELTMIND sync disabled or source directory unavailable",
            "celtmind_path": str(settings.celtmind_path),
        }

    client = get_supabase_client(settings)
    sync_repository = SyncRepository(client)
    rag_service = RagService(
        settings=settings,
        cache=CacheClient(settings),
        repository=RagRepository(client),
        report_repository=ReportRepository(client),
        profile_repository=ProfileRepository(client),
        llm_provider=OpenAIProvider(settings),
        ops_service=OpsService(OpsRepository(client)),
    )
    sync_service = CeltmindSyncService(
        sync_repository=sync_repository,
        assessment_repository=AssessmentRepository(client),
        skill_repository=SkillRepository(client),
        rag_service=rag_service,
        event_service=DomainEventService(sync_repository),
        celtmind_path=settings.celtmind_path,
    )
    mark_worker_heartbeat()
    try:
        return asyncio.run(sync_service.sync())
    except Exception as exc:
        if self.request.retries >= 3:
            asyncio.run(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.run_celtmind_sync",
                    task_id=getattr(self.request, "id", None),
                    entity_type="celtmind_ingestion",
                    entity_id=None,
                    payload={"celtmind_path": str(settings.celtmind_path)},
                    error=exc,
                    retry_count=self.request.retries,
                )
            )
        raise
