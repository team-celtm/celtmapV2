from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProfileRead(BaseModel):
    id: str
    email: str | None = None
    full_name: str | None = None
    headline: str | None = None
    focus_role: str | None = None
    weekly_goal: str | None = None
    avatar_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    focus_role: str | None = None
    weekly_goal: str | None = None
    avatar_url: str | None = None
    metadata: dict[str, Any] | None = None


class UserPreferenceRead(BaseModel):
    user_id: str
    desktop_notifications: bool = True
    weekly_digest: bool = True
    folio_reminders: bool = True
    folio_focus: str | None = None
    security_mode: str = "standard"
    updated_at: datetime | None = None


class UserPreferenceUpdate(BaseModel):
    desktop_notifications: bool | None = None
    weekly_digest: bool | None = None
    folio_reminders: bool | None = None
    folio_focus: str | None = None


class SecuritySettingsUpdate(BaseModel):
    security_mode: str = Field(default="standard")


class ArtifactRead(BaseModel):
    id: str
    user_id: str
    bucket_name: str | None = None
    storage_path: str | None = None
    file_name: str
    file_type: str
    file_url: str | None = None
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
