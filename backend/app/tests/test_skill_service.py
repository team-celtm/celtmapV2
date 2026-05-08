from __future__ import annotations

import pytest

from app.services.skill_service import SkillService


class FakeSkillRepository:
    async def list_user_skills(self, user_id: str) -> list[dict]:
        return [
            {"skill_name": "Python", "proficiency_score": 90.0},
            {"skill_name": "SQL", "proficiency_score": 80.0},
        ]

    async def list_hidden_candidates(self, user_id: str) -> list[dict]:
        return []

    async def list_roles(self) -> list[dict]:
        return [
            {"id": "role-ml", "role_name": "ML Engineer"},
            {"id": "role-da", "role_name": "Data Analyst"},
        ]

    async def list_role_requirements(self, role_id: str | None = None) -> list[dict]:
        requirements = {
            "role-ml": [
                {"skill_name": "Python", "weight": 0.7},
                {"skill_name": "SQL", "weight": 0.3},
            ],
            "role-da": [
                {"skill_name": "SQL", "weight": 0.8},
                {"skill_name": "Dashboarding", "weight": 0.2},
            ],
        }
        return requirements.get(role_id or "", [])


class FakeEventService:
    async def emit(self, **kwargs) -> dict:
        return kwargs


@pytest.mark.asyncio
async def test_get_role_fit_prefers_highest_weighted_match() -> None:
    service = SkillService(FakeSkillRepository(), FakeEventService())
    result = await service.get_role_fit("user-1")

    assert result["role_name"] == "ML Engineer"
    assert result["fit_score"] == 87.0


def test_compute_weighted_skill_score_renormalizes_missing_sources() -> None:
    service = SkillService(FakeSkillRepository(), FakeEventService())
    score = service.compute_weighted_skill_score(
        assessment_score=80.0,
        written_score=None,
        interview_score=None,
        artifact_score=100.0,
    )

    assert score == 86.0
