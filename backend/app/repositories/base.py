from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any, cast

import httpx
from supabase import Client

from app.core.pagination import decode_cursor

RowList = list[dict[str, Any]]
logger = logging.getLogger(__name__)


class SupabaseTableRepository:
    def __init__(self, client: Client, table_name: str) -> None:
        self.client = client
        self.table_name = table_name

    async def _run(self, operation: Callable[[], Any]) -> Any:
        return await asyncio.to_thread(operation)

    async def _run_read(self, operation: Callable[[], Any]) -> Any:
        max_attempts = 1

        for attempt in range(1, max_attempts + 1):
            try:
                return await self._run(operation)
            except httpx.TransportError as exc:
                if attempt == max_attempts:
                    raise

                delay_seconds = 0.2 * attempt
                logger.warning(
                    "Transient Supabase read failure on %s (attempt %s/%s): %s",
                    self.table_name,
                    attempt,
                    max_attempts,
                    exc,
                )
                await asyncio.sleep(delay_seconds)

    async def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            result = self.client.table(self.table_name).insert(payload).execute()
            data = cast(RowList, result.data or [])
            if not data:
                logger.error("Supabase insert for %s returned no data. Result: %s", self.table_name, result)
                return {}
            return data[0]

        return await self._run(operation)

    async def upsert(
        self, payload: dict[str, Any] | list[dict[str, Any]], on_conflict: str
    ) -> list[dict[str, Any]]:
        if isinstance(payload, list) and not payload:
            return []

        def operation() -> list[dict[str, Any]]:
            result = (
                self.client.table(self.table_name)
                .upsert(
                    payload,
                    on_conflict=on_conflict,
                )
                .execute()
            )
            return cast(RowList, result.data or [])

        return await self._run(operation)

    async def get_one(
        self, *, filters: dict[str, Any], columns: str = "*"
    ) -> dict[str, Any] | None:
        def operation() -> dict[str, Any] | None:
            query = self.client.table(self.table_name).select(columns).limit(1)
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.execute()
            data = cast(RowList, result.data or [])
            return data[0] if data else None

        return await self._run_read(operation)

    async def get_by_id(self, record_id: str, columns: str = "*") -> dict[str, Any] | None:
        return await self.get_one(filters={"id": record_id}, columns=columns)

    async def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        columns: str = "*",
        order_by: str = "created_at",
        descending: bool = True,
        limit: int = 25,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        decoded_cursor = decode_cursor(cursor)

        def operation() -> list[dict[str, Any]]:
            query = (
                self.client.table(self.table_name)
                .select(columns)
                .order(order_by, desc=descending)
                .limit(limit)
            )
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            if decoded_cursor and decoded_cursor.get(order_by):
                cursor_value = decoded_cursor[order_by]
                comparator = query.lt if descending else query.gt
                query = comparator(order_by, cursor_value)
            result = query.execute()
            return cast(RowList, result.data or [])

        return await self._run_read(operation)

    async def list_where_in(
        self,
        *,
        column: str,
        values: Sequence[Any],
        columns: str = "*",
    ) -> RowList:
        if not values:
            return []

        def operation() -> RowList:
            result = (
                self.client.table(self.table_name).select(columns).in_(column, values).execute()
            )
            return cast(RowList, result.data or [])

        return await self._run_read(operation)

    async def update(
        self, *, filters: dict[str, Any], payload: dict[str, Any]
    ) -> RowList:
        def operation() -> RowList:
            query = self.client.table(self.table_name).update(payload)
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.execute()
            return cast(RowList, result.data or [])

        return await self._run(operation)

    async def delete(self, *, filters: dict[str, Any]) -> RowList:
        def operation() -> RowList:
            query = self.client.table(self.table_name).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.execute()
            return cast(RowList, result.data or [])

        return await self._run(operation)
