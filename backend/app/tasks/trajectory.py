from __future__ import annotations

import asyncio
import concurrent.futures
from app.utils.async_runner import run_async
from typing import Any

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.learning_repository import LearningRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.domain_event_service import DomainEventService
from app.services.learning_service import LearningService
from app.services.skill_request_service import SkillRequestService
from app.services.skill_service import SkillService
from app.services.trajectory_service import TrajectoryService
from app.tasks.celery_app import celery_app
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure




@celery_app.task(
    bind=True,
    name="app.tasks.bootstrap_user_trajectory",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def bootstrap_user_trajectory(self: Any, user_id: str, role_name: str | None = None) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    mark_worker_heartbeat()

    try:
        return run_async(_bootstrap_trajectory(user_id, role_name, client))
    except Exception as exc:
        if self.request.retries >= 3:
            run_async(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.bootstrap_user_trajectory",
                    task_id=getattr(self.request, "id", None),
                    entity_type="trajectory",
                    entity_id=user_id,
                    payload={"user_id": user_id, "role_name": role_name},
                    error=exc,
                    retry_count=self.request.retries,
                )
            )
        raise


async def _bootstrap_trajectory(user_id: str, role_name: str | None, client: Any) -> dict:
    learning_repo = LearningRepository(client)
    profile_repo = ProfileRepository(client)
    skill_repo = SkillRepository(client)
    event_service = DomainEventService(SyncRepository(client))
    skill_service = SkillService(skill_repo, event_service)
    
    # We need to build a full TrajectoryService here or its equivalent
    # Instead of duplicating, we can try to use dependencies if possible, 
    # but in Celery we typically instantiate manually.
    
    from app.services.rag_service import RagService
    from app.integrations.cache import CacheClient
    from app.integrations.llm import OpenAIProvider
    from app.repositories.rag_repository import RagRepository
    from app.repositories.report_repository import ReportRepository
    from app.repositories.ops_repository import OpsRepository
    from app.services.ops_service import OpsService
    from app.services.schedule_service import ScheduleService
    from app.repositories.schedule_repository import ScheduleRepository
    
    settings = get_settings()
    cache = CacheClient(settings)
    rag_service = RagService(
        settings=settings,
        cache=cache,
        repository=RagRepository(client),
        report_repository=ReportRepository(client),
        llm_provider=OpenAIProvider(settings),
        ops_service=OpsService(OpsRepository(client))
    )
    
    learning_service = LearningService(learning_repo, skill_service, rag_service)
    schedule_service = ScheduleService(ScheduleRepository(client))
    skill_request_service = SkillRequestService(
        repository=skill_repo,
        assessment_repository=None, # Not needed for bootstrap
        rag_service=rag_service,
        llm_provider=rag_service.llm_provider,
        ops_service=rag_service.ops_service,
        schedule_service=schedule_service,
        event_service=event_service
    )
    
    trajectory_service = TrajectoryService(
        repository=learning_repo,
        profile_repository=profile_repo,
        skill_repository=skill_repo,
        skill_service=skill_service,
        learning_service=learning_service,
        skill_request_service=skill_request_service,
        event_service=event_service
    )
    
    result = await trajectory_service.bootstrap_user_path(user_id, role_name)
    await rag_service.llm_provider.close()
    return result
