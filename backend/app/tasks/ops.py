from __future__ import annotations

import traceback
from typing import Any

from app.config.settings import Settings
from app.integrations.cache import CacheClient
from app.integrations.supabase import get_supabase_client
from app.observability.metrics import metrics
from app.repositories.ops_repository import OpsRepository
from app.services.ops_service import OpsService


def mark_worker_heartbeat() -> None:
    metrics.heartbeat_worker()


async def persist_job_failure(
    *,
    settings: Settings,
    task_name: str,
    task_id: str | None,
    entity_type: str | None,
    entity_id: str | None,
    payload: dict[str, Any],
    error: BaseException,
    retry_count: int,
) -> None:
    cache = CacheClient(settings)
    client = get_supabase_client(settings)
    ops_service = OpsService(OpsRepository(client))
    stack = traceback.format_exc()
    failure_payload = {
        "task_name": task_name,
        "task_id": task_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload,
        "error_message": str(error),
        "traceback": stack,
        "retry_count": retry_count,
        "status": "failed",
    }
    await ops_service.log_job_failure(
        task_name=task_name,
        task_id=task_id,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        error_message=str(error),
        traceback_text=stack,
        retry_count=retry_count,
    )
    cache.push_dead_letter(settings.dead_letter_queue_name, failure_payload)
    metrics.record_worker_failure()
