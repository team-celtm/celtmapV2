from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.ops_repository import OpsRepository


class OpsService:
    def __init__(self, repository: OpsRepository) -> None:
        self.repository = repository

    async def log_ai_call(
        self,
        *,
        user_id: str | None,
        provider: str,
        model: str,
        operation: str,
        prompt_hash: str | None,
        cache_hit: bool,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        status: str,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        return await self.repository.create_ai_call_log(
            {
                "user_id": user_id,
                "provider": provider,
                "model": model,
                "operation": operation,
                "prompt_hash": prompt_hash,
                "cache_hit": cache_hit,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "status": status,
                "source_entity_type": source_entity_type,
                "source_entity_id": source_entity_id,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def log_job_failure(
        self,
        *,
        task_name: str,
        task_id: str | None,
        error_message: str,
        traceback: str | None,
        retry_count: int,
        entity_type: str | None = None,
        entity_id: str | None = None,
        payload: dict | None = None,
    ) -> dict:
        return await self.repository.create_job_failure(
            {
                "task_name": task_name,
                "task_id": task_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload or {},
                "error_message": error_message,
                "traceback": traceback,
                "retry_count": retry_count,
                "status": "failed",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def recent_job_failures(self, limit: int = 20) -> list[dict]:
        return await self.repository.list_recent_job_failures(limit=limit)
