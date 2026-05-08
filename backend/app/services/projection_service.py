from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.report_repository import ReportRepository
from app.services.dashboard_service import DashboardService


class ProjectionService:
    def __init__(self, repository: ReportRepository, dashboard_service: DashboardService) -> None:
        self.repository = repository
        self.dashboard_service = dashboard_service

    async def refresh_dashboard_projection(self, user_id: str) -> dict:
        payload = await self.dashboard_service.build_summary_payload(user_id)
        return await self.repository.upsert_projection(
            {
                "user_id": user_id,
                "payload": payload,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
