from __future__ import annotations

import pytest

from app.services.graph_sync_service import GraphSyncService


class FakeSkillRepository:
    async def list_user_skills(self, user_id: str) -> list[dict]:
        return [
            {
                "skill_id": "python",
                "skill_name": "Python",
                "proficiency_score": 92.5,
            }
        ]

    async def list_roles(self) -> list[dict]:
        return [{"role_name": "ML Engineer", "description": "Builds ML systems"}]

    async def list_role_requirements(self, role_name: str | None = None) -> list[dict]:
        return [
            {
                "role_name": "ML Engineer",
                "skill_name": "Python",
                "weight": 0.6,
                "prerequisite_skill_name": "Programming Fundamentals",
            }
        ]


class FakeNeo4jSession:
    def __init__(self, calls: list[tuple[str, dict]]) -> None:
        self.calls = calls

    async def __aenter__(self) -> FakeNeo4jSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def run(self, query: str, **params) -> None:
        self.calls.append((query, params))


class FakeNeo4jDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def session(self) -> FakeNeo4jSession:
        return FakeNeo4jSession(self.calls)


@pytest.mark.asyncio
async def test_sync_user_projects_roles_requirements_and_prerequisites() -> None:
    driver = FakeNeo4jDriver()
    service = GraphSyncService(FakeSkillRepository(), driver)

    await service.sync_user("user-1", event_id="evt-123")

    assert any("HAS_SKILL" in query for query, _ in driver.calls)
    assert any("REQUIRED_FOR" in query for query, _ in driver.calls)
    assert any("DEPENDS_ON" in query for query, _ in driver.calls)
    assert any(params.get("event_id") == "evt-123" for _, params in driver.calls)

