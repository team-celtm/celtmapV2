from __future__ import annotations

from supabase import Client

from app.repositories.base import SupabaseTableRepository


class ReportRepository:
    def __init__(self, client: Client) -> None:
        self.reports = SupabaseTableRepository(client, "reports")
        self.projections = SupabaseTableRepository(client, "dashboard_projections")

    async def create_report(self, payload: dict) -> dict:
        return await self.reports.insert(payload)

    async def get_latest_report(self, user_id: str) -> dict | None:
        rows = await self.reports.list(filters={"user_id": user_id}, limit=1)
        return rows[0] if rows else None

    async def upsert_projection(self, payload: dict) -> dict:
        rows = await self.projections.upsert(payload, on_conflict="user_id")
        return rows[0] if rows else payload

    async def get_projection(self, user_id: str) -> dict | None:
        return await self.projections.get_one(filters={"user_id": user_id})
