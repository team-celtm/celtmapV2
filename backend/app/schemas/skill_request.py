from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SkillRequestCreate(BaseModel):
    requested_name: str = Field(min_length=2, max_length=160)
    requested_type: str = Field(default="skill", min_length=2, max_length=40)
    description: str | None = Field(default=None, max_length=4000)


class SkillRequestAdminOverride(BaseModel):
    decision: Literal["promote", "reject"]
    reason: str | None = Field(default=None, max_length=500)


class SkillRequestRead(BaseModel):
    id: str
    user_id: str
    requested_name: str
    normalized_name: str
    requested_type: str
    matched_skill_id: str | None = None
    status: str
    generation_status: str
    generated_payload: dict[str, Any] = Field(default_factory=dict)
    mcq_score: float | None = None
    written_score: float | None = None
    interview_score: float | None = None
    overall_score: float | None = None
    promoted_skill_id: str | None = None
    promoted_at: datetime | None = None
    rejected_at: datetime | None = None
    admin_override_status: str | None = None
    admin_override_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
