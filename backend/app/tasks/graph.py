from __future__ import annotations

import asyncio
from typing import Any

from app.config.settings import get_settings
from app.integrations.neo4j_client import get_neo4j_driver
from app.integrations.supabase import get_supabase_client
from app.repositories.skill_repository import SkillRepository
from app.services.graph_sync_service import GraphSyncService
from app.tasks.celery_app import celery_app
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure


@celery_app.task(
    bind=True,
    name="app.tasks.sync_user_graph",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def sync_user_graph(self: Any, user_id: str, event_id: str | None = None) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    service = GraphSyncService(SkillRepository(client), get_neo4j_driver(settings))
    mark_worker_heartbeat()
    try:
        asyncio.run(service.sync_user(user_id, event_id=event_id))
        return {"status": "completed", "user_id": user_id, "event_id": event_id}
    except Exception as exc:
        if self.request.retries >= 3:
            asyncio.run(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.sync_user_graph",
                    task_id=getattr(self.request, "id", None),
                    entity_type="graph_sync",
                    entity_id=user_id,
                    payload={"user_id": user_id, "event_id": event_id},
                    error=exc,
                    retry_count=self.request.retries,
                )
            )
        raise
