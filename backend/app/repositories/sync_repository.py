from __future__ import annotations

from typing import cast

from supabase import Client

from app.models.enums import DomainEventStatus
from app.repositories.base import SupabaseTableRepository


class SyncRepository:
    def __init__(self, client: Client) -> None:
        self.file_registry = SupabaseTableRepository(client, "celtmind_file_registry")
        self.runs = SupabaseTableRepository(client, "celtmind_ingestion_runs")
        self.events = SupabaseTableRepository(client, "domain_events")

    async def get_file_registry(self, file_name: str) -> dict | None:
        return await self.file_registry.get_one(filters={"file_name": file_name})

    async def upsert_file_registry(self, payload: dict) -> dict:
        rows = await self.file_registry.upsert(payload, on_conflict="file_name")
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    async def create_run(self, payload: dict) -> dict:
        return await self.runs.insert(payload)

    async def update_run(self, run_id: str, payload: dict) -> dict:
        rows = await self.runs.update(filters={"id": run_id}, payload=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    async def create_event(self, payload: dict) -> dict:
        return await self.events.insert(payload)

    async def update_event(self, event_id: str, payload: dict) -> dict:
        rows = await self.events.update(filters={"id": event_id}, payload=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    async def list_pending_events(self, limit: int = 100) -> list[dict]:
        return await self.events.list(
            filters={"status": DomainEventStatus.PENDING.value},
            limit=limit,
        )

    async def list_retryable_events(self, limit: int = 100, max_retry_count: int = 5) -> list[dict]:
        def operation() -> list[dict]:
            result = (
                self.events.client.table(self.events.table_name)
                .select("*")
                .in_(
                    "status",
                    [
                        DomainEventStatus.PENDING.value,
                        DomainEventStatus.FAILED.value,
                    ],
                )
                .lt("retry_count", max_retry_count)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return cast(list[dict], result.data or [])

        return await self.events._run(operation)

    async def get_event(self, event_id: str) -> dict | None:
        return await self.events.get_by_id(event_id)
