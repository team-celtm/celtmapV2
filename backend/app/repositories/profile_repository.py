from __future__ import annotations

from typing import Any

from supabase import Client

from app.repositories.base import SupabaseTableRepository


class ProfileRepository:
    def __init__(self, client: Client) -> None:
        self.users = SupabaseTableRepository(client, "users")
        self.profiles = SupabaseTableRepository(client, "profiles")
        self.preferences = SupabaseTableRepository(client, "user_preferences")
        self.artifacts = SupabaseTableRepository(client, "uploaded_artifacts")

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        return await self.users.get_by_id(user_id)

    async def upsert_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self.users.upsert(payload, on_conflict="id")
        if isinstance(rows, list) and rows:
            return rows[0]
        return await self.users.get_by_id(str(payload["id"])) or payload

    async def get_profile(self, user_id: str) -> dict[str, Any] | None:
        return await self.profiles.get_by_id(user_id)

    async def upsert_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self.profiles.upsert(payload, on_conflict="id")
        if isinstance(rows, list) and rows:
            return rows[0]
        return await self.profiles.get_by_id(str(payload["id"])) or payload

    async def get_preferences(self, user_id: str) -> dict[str, Any] | None:
        return await self.preferences.get_one(filters={"user_id": user_id})

    async def upsert_preferences(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self.preferences.upsert(payload, on_conflict="user_id")
        if isinstance(rows, list) and rows:
            return rows[0]
        return await self.preferences.get_one(filters={"user_id": payload["user_id"]}) or payload

    async def insert_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.artifacts.insert(payload)

    async def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        return await self.artifacts.get_by_id(artifact_id)

    async def update_artifact(self, artifact_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self.artifacts.update(filters={"id": artifact_id}, payload=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    async def list_artifacts(self, user_id: str, limit: int = 25) -> list[dict[str, Any]]:
        return await self.artifacts.list(filters={"user_id": user_id}, limit=limit)

    async def delete_artifact(self, artifact_id: str) -> None:
        await self.artifacts.delete(filters={"id": artifact_id})
