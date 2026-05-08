from __future__ import annotations

from supabase import Client

from app.repositories.base import SupabaseTableRepository


class OpsRepository:
    def __init__(self, client: Client) -> None:
        self.ai_call_logs = SupabaseTableRepository(client, "ai_call_logs")
        self.job_failures = SupabaseTableRepository(client, "job_failures")

    async def create_ai_call_log(self, payload: dict) -> dict:
        return await self.ai_call_logs.insert(payload)

    async def create_job_failure(self, payload: dict) -> dict:
        return await self.job_failures.insert(payload)

    async def list_recent_job_failures(self, limit: int = 20) -> list[dict]:
        return await self.job_failures.list(limit=limit)
