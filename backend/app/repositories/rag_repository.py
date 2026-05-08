from __future__ import annotations

import asyncio
from typing import Any, cast

from supabase import Client

from app.repositories.base import SupabaseTableRepository


class RagRepository:
    def __init__(self, client: Client) -> None:
        self.client = client
        self.knowledge = SupabaseTableRepository(client, "rag_knowledge")

    async def search_knowledge(
        self,
        *,
        query_embedding: list[float],
        user_id: str | None = None,
        threshold: float = 0.25,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        def operation() -> list[dict[str, Any]]:
            response = self.client.rpc(
                "search_rag_knowledge",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                    "p_user_id": user_id,
                },
            ).execute()
            return cast(list[dict[str, Any]], response.data or [])

        return await asyncio.to_thread(operation)

    async def upsert_knowledge(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payloads:
            return []
        # In rag_documents, we use dedupe_hash to prevent duplicates
        return await self.knowledge.upsert(payloads, on_conflict="dedupe_hash")

    async def archive_stale_user_knowledge(self, user_id: str, keep_count: int) -> int:
        def operation() -> int:
            response = self.client.rpc(
                "archive_stale_user_rag_knowledge",
                {"p_user_id": user_id, "p_keep_count": keep_count},
            ).execute()
            return int(response.data or 0)

        return await asyncio.to_thread(operation)

    async def list_knowledge(
        self,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self.knowledge.list(filters=filters, limit=limit)

    async def update_knowledge(self, knowledge_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self.knowledge.update(filters={"id": knowledge_id}, payload=payload)
        return rows[0] if rows else payload
