from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.schedule_repository import ScheduleRepository


class ScheduleService:
    def __init__(self, repository: ScheduleRepository) -> None:
        self.repository = repository

    async def create_event(self, user_id: str, payload: dict) -> dict:
        return await self.repository.create_event(
            {
                "user_id": user_id,
                **payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def ensure_event(self, user_id: str, payload: dict[str, Any]) -> dict:
        title = str(payload["title"])
        event_type = str(payload["event_type"])
        existing = await self.repository.get_event(
            user_id=user_id,
            title=title,
            event_type=event_type,
        )
        event_payload = {
            "user_id": user_id,
            **payload,
        }
        if existing is None:
            event_payload["created_at"] = datetime.now(timezone.utc).isoformat()
            return await self.repository.create_event(event_payload)
        return await self.repository.update_event(existing["id"], event_payload)

    async def list_events(self, user_id: str, limit: int, cursor: str | None) -> list[dict]:
        return await self.repository.list_events(user_id=user_id, limit=limit, cursor=cursor)

    async def update_event(self, user_id: str, event_id: str, payload: dict) -> dict | None:
        existing = await self.repository.get_event_by_id(event_id)
        if existing is None or existing.get("user_id") != user_id:
            return None

        update_payload = {
            key: value
            for key, value in payload.items()
            if value is not None
        }
        if not update_payload:
            return existing

        return await self.repository.update_event(event_id, update_payload)

    async def delete_event(self, user_id: str, event_id: str) -> dict | None:
        existing = await self.repository.get_event_by_id(event_id)
        if existing is None or existing.get("user_id") != user_id:
            return None
        return await self.repository.delete_event(event_id)
