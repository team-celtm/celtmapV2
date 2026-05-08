from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import HiddenSkillStatus


class SkillRead(BaseModel):
    skill_id: str
    skill_name: str
    verified_score: float
    assessment_score: float | None = None
    interview_score: float | None = None
    artifact_score: float | None = None
    updated_at: datetime | None = None


class HiddenSkillCandidateRead(BaseModel):
    id: str
    skill_name: str
    confidence_score: float
    source: str
    evidence: str
    artifact_id: str | None = None
    status: HiddenSkillStatus
    created_at: datetime | None = None


class RoleFitRead(BaseModel):
    role_name: str
    fit_score: float
    matched_skills: list[str]
    missing_skills: list[str]


class SkillGapRead(BaseModel):
    skill_name: str
    target_weight: float
    user_score: float
    gap_severity: float
