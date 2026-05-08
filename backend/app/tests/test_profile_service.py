from __future__ import annotations

import pytest

from app.services.profile_service import ProfileService


class FakeProfileRepository:
    def __init__(self) -> None:
        self.profile: dict | None = None
        self.user: dict | None = None

    async def get_profile(self, user_id: str) -> dict | None:
        if self.profile and self.profile["id"] == user_id:
            return self.profile
        return None

    async def upsert_profile(self, payload: dict) -> dict:
        merged = {**(self.profile or {}), **payload}
        self.profile = merged
        return merged

    async def get_user(self, user_id: str) -> dict | None:
        if self.user and self.user["id"] == user_id:
            return self.user
        return None

    async def upsert_user(self, payload: dict) -> dict:
        merged = {**(self.user or {}), **payload}
        self.user = merged
        return merged


class FakeEventService:
    async def emit(self, **kwargs) -> dict:
        return kwargs


@pytest.mark.asyncio
async def test_get_profile_creates_matching_legacy_user_record() -> None:
    repository = FakeProfileRepository()
    service = ProfileService(repository, client=None, event_service=FakeEventService())

    profile = await service.get_profile(
        "user-1",
        email="codex@example.com",
    )

    assert profile["id"] == "user-1"
    assert repository.user is not None
    assert repository.user["id"] == "user-1"
    assert repository.user["email"] == "codex@example.com"


@pytest.mark.asyncio
async def test_update_profile_syncs_legacy_user_role_and_preserves_existing_fields() -> None:
    repository = FakeProfileRepository()
    repository.profile = {
        "id": "user-2",
        "email": "sync@example.com",
        "full_name": "Sync Tester",
        "headline": None,
        "created_at": "2026-04-14T10:00:00+00:00",
    }
    repository.user = {
        "id": "user-2",
        "email": "sync@example.com",
        "full_name": "Sync Tester",
        "avatar_url": "profile-assets/user-2/avatar.png",
        "role": "student",
        "target_role_id": "target-role-1",
        "created_at": "2026-04-14T10:00:00+00:00",
    }
    service = ProfileService(repository, client=None, event_service=FakeEventService())

    updated = await service.update_profile(
        "user-2",
        {
            "headline": "AI Engineer",
        },
    )

    assert updated["headline"] == "AI Engineer"
    assert repository.user is not None
    assert repository.user["role"] == "AI Engineer"
    assert repository.user["avatar_url"] == "profile-assets/user-2/avatar.png"
    assert repository.user["target_role_id"] == "target-role-1"
