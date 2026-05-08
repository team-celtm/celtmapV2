from __future__ import annotations

from app.models.enums import DomainEventStatus, DomainEventType
from app.repositories.sync_repository import SyncRepository


class DomainEventService:
    def __init__(self, repository: SyncRepository) -> None:
        self.repository = repository

    async def emit(
        self,
        *,
        event_type: DomainEventType,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict,
    ) -> dict:
        return await self.repository.create_event(
            {
                "event_type": event_type.value,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "status": DomainEventStatus.PENDING.value,
                "payload": payload,
            }
        )
