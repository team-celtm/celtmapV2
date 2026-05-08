from __future__ import annotations

import pytest

from app.services.trajectory_service import TrajectoryService


class FakeLearningRepository:
    async def upsert_trajectory_roles(self, payloads: list[dict]) -> list[dict]:
        return payloads


class FakeProfileRepository:
    async def get_profile(self, user_id: str) -> dict:
        return {
            "focus_role": "ML Engineer",
            "metadata": {},
        }

    async def list_artifacts(self, user_id: str, limit: int = 50) -> list[dict]:
        return []


class FakeSkillRepository:
    async def list_role_requirements(self, role_name: str | None = None) -> list[dict]:
        return []

    async def list_active_skills(self, limit: int = 500) -> list[dict]:
        return []

    async def list_user_skills(self, user_id: str) -> list[dict]:
        return []


class FakeSkillService:
    async def get_role_fit(self, user_id: str) -> dict:
        return {
            "role_name": "ML Engineer",
            "fit_score": 64.0,
        }

    async def record_skill_measurement(self, **kwargs) -> dict:
        return kwargs


class FakeLearningService:
    async def get_learning_path(self, user_id: str, role_name: str) -> dict:
        return {
            "role_name": role_name,
            "modules": [
                {
                    "week": 1,
                    "skill_name": "Machine Learning Fundamentals",
                    "gap_severity": 0.7,
                    "resources": [],
                }
            ],
        }


class ExplodingSkillRequestService:
    async def create_request(self, **kwargs) -> dict:
        raise AssertionError("Skill requests should not be auto-created during bootstrap")


class FakeEventService:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, **kwargs) -> None:
        self.events.append(kwargs)


@pytest.mark.asyncio
async def test_bootstrap_user_path_skips_auto_generating_skill_requests() -> None:
    event_service = FakeEventService()
    service = TrajectoryService(
        repository=FakeLearningRepository(),  # type: ignore[arg-type]
        profile_repository=FakeProfileRepository(),  # type: ignore[arg-type]
        skill_repository=FakeSkillRepository(),  # type: ignore[arg-type]
        skill_service=FakeSkillService(),  # type: ignore[arg-type]
        learning_service=FakeLearningService(),  # type: ignore[arg-type]
        skill_request_service=ExplodingSkillRequestService(),  # type: ignore[arg-type]
        event_service=event_service,  # type: ignore[arg-type]
    )

    result = await service.bootstrap_user_path("user-1", role_name="ML Engineer")

    assert result["role_name"] == "ML Engineer"
    assert result["skill_request_names"] == []
    assert result["modules"][0]["skill_name"] == "Machine Learning Fundamentals"
    assert len(event_service.events) == 1
