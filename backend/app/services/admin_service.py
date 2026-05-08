from __future__ import annotations

from app.repositories.sync_repository import SyncRepository
from app.services.celtmind_sync import CeltmindSyncService


class AdminService:
    def __init__(self, sync_service: CeltmindSyncService, sync_repository: SyncRepository) -> None:
        self.sync_service = sync_service
        self.sync_repository = sync_repository

    async def sync_celtmind(self) -> dict:
        return await self.sync_service.sync()

    async def get_sync_status(self) -> dict:
        runs = await self.sync_repository.runs.list(limit=1)
        if not runs:
            return {"status": "never_run", "files": []}
        return runs[0]
