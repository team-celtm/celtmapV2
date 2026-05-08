from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.profile_repository import ProfileRepository


class SettingsService:
    def __init__(self, repository: ProfileRepository) -> None:
        self.repository = repository

    async def get_settings(self, user_id: str) -> dict:
        settings = await self.repository.get_preferences(user_id)
        if settings:
            return settings
        return await self.repository.upsert_preferences(
            {
                "user_id": user_id,
                "desktop_notifications": True,
                "weekly_digest": True,
                "folio_reminders": True,
                "security_mode": "standard",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def update_settings(self, user_id: str, payload: dict) -> dict:
        return await self.repository.upsert_preferences(
            {
                "user_id": user_id,
                **payload,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
