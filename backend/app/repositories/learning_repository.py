from __future__ import annotations

from supabase import Client

from app.repositories.base import SupabaseTableRepository


class LearningRepository:
    def __init__(self, client: Client) -> None:
        self.paths = SupabaseTableRepository(client, "learning_paths")
        self.modules = SupabaseTableRepository(client, "learning_modules")
        self.trajectories = SupabaseTableRepository(client, "trajectory_roles")

    async def get_latest_path(self, user_id: str, role_name: str) -> dict | None:
        rows = await self.paths.list(
            filters={"user_id": user_id, "role_name": role_name},
            limit=1,
            order_by="created_at",
            descending=True,
        )
        return rows[0] if rows else None

    async def list_path_modules(self, path_id: str) -> list[dict]:
        return await self.modules.list(filters={"path_id": path_id}, limit=100, order_by="week")

    async def create_path(self, payload: dict) -> dict:
        return await self.paths.insert(payload)

    async def upsert_modules(self, payloads: list[dict]) -> list[dict]:
        return await self.modules.upsert(payloads, on_conflict="path_id,title")

    async def list_trajectory_roles(self, user_id: str) -> list[dict]:
        return await self.trajectories.list(
            filters={"user_id": user_id},
            limit=50,
            order_by="updated_at",
        )

    async def upsert_trajectory_roles(self, payloads: list[dict]) -> list[dict]:
        return await self.trajectories.upsert(payloads, on_conflict="user_id,role_name")
