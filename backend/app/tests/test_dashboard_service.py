from __future__ import annotations

import pytest

from app.services.dashboard_service import DashboardService


class FakeReportRepository:
    def __init__(self, projection: dict | None = None) -> None:
        self.projection = projection
        self.upsert_payloads: list[dict] = []

    async def get_projection(self, user_id: str) -> dict | None:
        return self.projection

    async def upsert_projection(self, payload: dict) -> dict:
        self.upsert_payloads.append(payload)
        self.projection = {"user_id": payload["user_id"], "payload": payload["payload"]}
        return self.projection

    async def get_latest_report(self, user_id: str) -> dict | None:
        return {
            "id": "report-1",
            "created_at": "2026-04-14T12:00:00+00:00",
        }


class FakeSkillService:
    async def get_role_fit(self, user_id: str) -> dict:
        return {"role_name": "ML Engineer", "fit_score": 81.0}

    async def list_user_skills(self, user_id: str) -> list[dict]:
        return [
            {"skill_name": "Python", "proficiency_score": 91.0},
            {"skill_name": "ML Ops", "proficiency_score": 74.0},
        ]

    async def list_hidden_candidates(self, user_id: str) -> list[dict]:
        return [{"status": "pending"}, {"status": "approved"}]


class FakeScheduleService:
    async def list_events(self, user_id: str, limit: int, cursor: str | None) -> list[dict]:
        return [{"id": "event-1", "title": "Validate Python"}]


@pytest.mark.asyncio
async def test_get_summary_persists_projection_when_missing() -> None:
    repository = FakeReportRepository()
    service = DashboardService(
        report_repository=repository,  # type: ignore[arg-type]
        skill_service=FakeSkillService(),  # type: ignore[arg-type]
        schedule_service=FakeScheduleService(),  # type: ignore[arg-type]
    )

    summary = await service.get_summary("user-1")

    assert summary["user_id"] == "user-1"
    assert summary["top_skills"] == ["Python", "ML Ops"]
    assert summary["pending_hidden_skills"] == 1
    assert summary["latest_report_id"] == "report-1"
    assert len(repository.upsert_payloads) == 1
    assert repository.upsert_payloads[0]["payload"] == summary


@pytest.mark.asyncio
async def test_get_summary_uses_existing_projection_without_recomputing() -> None:
    repository = FakeReportRepository(
        projection={
            "user_id": "user-1",
            "payload": {
                "user_id": "user-1",
                "readiness_score": 55.0,
                "role_fit": 55.0,
                "top_skills": ["Stored skill"],
                "pending_hidden_skills": 0,
                "next_event": None,
                "latest_report_id": None,
                "latest_report_created_at": None,
            },
        }
    )
    service = DashboardService(
        report_repository=repository,  # type: ignore[arg-type]
        skill_service=FakeSkillService(),  # type: ignore[arg-type]
        schedule_service=FakeScheduleService(),  # type: ignore[arg-type]
    )

    summary = await service.get_summary("user-1")

    assert summary["top_skills"] == ["Stored skill"]
    assert repository.upsert_payloads == []


@pytest.mark.asyncio
async def test_get_summary_sorts_top_skills_by_proficiency_score() -> None:
    repository = FakeReportRepository()

    class UnsortedSkillService(FakeSkillService):
        async def list_user_skills(self, user_id: str) -> list[dict]:
            return [
                {"skill_name": "Recently Updated", "proficiency_score": 12.0},
                {"skill_name": "Top Skill", "proficiency_score": 95.0},
                {"skill_name": "Mid Skill", "proficiency_score": 61.0},
            ]

    service = DashboardService(
        report_repository=repository,  # type: ignore[arg-type]
        skill_service=UnsortedSkillService(),  # type: ignore[arg-type]
        schedule_service=FakeScheduleService(),  # type: ignore[arg-type]
    )

    summary = await service.get_summary("user-1")

    assert summary["top_skills"] == ["Top Skill", "Mid Skill", "Recently Updated"]
