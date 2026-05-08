from __future__ import annotations

import pytest

from app.repositories.skill_repository import SkillRepository


@pytest.mark.asyncio
async def test_upsert_skill_catalog_populates_legacy_name() -> None:
    repository = SkillRepository(client=object())  # type: ignore[arg-type]
    captured: dict[str, object] = {}

    async def fake_upsert(payload: dict, on_conflict: str) -> list[dict]:
        captured["payload"] = payload
        captured["on_conflict"] = on_conflict
        return [payload]

    repository.skills.upsert = fake_upsert  # type: ignore[method-assign]

    result = await repository.upsert_skill_catalog(
        {
            "skill_name": "Algebra - Linear Equations",
            "normalized_name": "algebra-linear-equations",
        }
    )

    assert captured["on_conflict"] == "normalized_name"
    assert captured["payload"] == {
        "skill_name": "Algebra - Linear Equations",
        "normalized_name": "algebra-linear-equations",
        "name": "Algebra - Linear Equations",
    }
    assert result["name"] == "Algebra - Linear Equations"


@pytest.mark.asyncio
async def test_upsert_role_populates_legacy_name() -> None:
    repository = SkillRepository(client=object())  # type: ignore[arg-type]
    captured: dict[str, object] = {}

    async def fake_upsert(payload: dict, on_conflict: str) -> list[dict]:
        captured["payload"] = payload
        captured["on_conflict"] = on_conflict
        return [payload]

    repository.roles.upsert = fake_upsert  # type: ignore[method-assign]

    result = await repository.upsert_role(
        {
            "role_name": "Data Analyst",
            "normalized_name": "data-analyst",
        }
    )

    assert captured["on_conflict"] == "normalized_name"
    assert captured["payload"] == {
        "role_name": "Data Analyst",
        "normalized_name": "data-analyst",
        "name": "Data Analyst",
    }
    assert result["name"] == "Data Analyst"


@pytest.mark.asyncio
async def test_list_user_skills_orders_by_updated_at() -> None:
    repository = SkillRepository(client=object())  # type: ignore[arg-type]
    captured: dict[str, object] = {}

    async def fake_list(**kwargs: object) -> list[dict]:
        captured.update(kwargs)
        return []

    repository.user_skills.list = fake_list  # type: ignore[method-assign]

    await repository.list_user_skills("user-1")

    assert captured == {
        "filters": {"user_id": "user-1"},
        "limit": 500,
        "order_by": "updated_at",
    }
