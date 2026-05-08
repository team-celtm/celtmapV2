from __future__ import annotations

from supabase import Client

from app.repositories.base import SupabaseTableRepository


class ScheduleRepository:
    def __init__(self, client: Client) -> None:
        self.events = SupabaseTableRepository(client, "schedule_events")

    async def create_event(self, payload: dict) -> dict:
        return await self.events.insert(payload)

    async def get_event_by_id(self, event_id: str) -> dict | None:
        return await self.events.get_by_id(event_id)

    async def get_event(self, *, user_id: str, title: str, event_type: str) -> dict | None:
        return await self.events.get_one(
            filters={"user_id": user_id, "title": title, "event_type": event_type}
        )

    async def update_event(self, event_id: str, payload: dict) -> dict:
        rows = await self.events.update(filters={"id": event_id}, payload=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    async def list_events(
        self, user_id: str, limit: int = 100, cursor: str | None = None
    ) -> list[dict]:
        return await self.events.list(
            filters={"user_id": user_id},
            order_by="starts_at",
            descending=False,
            limit=limit,
            cursor=cursor,
        )

    async def delete_event(self, event_id: str) -> dict | None:
        rows = await self.events.delete(filters={"id": event_id})
        if isinstance(rows, list) and rows:
            return rows[0]
        return None
