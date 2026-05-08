from __future__ import annotations

from pydantic import BaseModel


class LearningResourceRead(BaseModel):
    title: str
    content: str
    resource_type: str
    skill_name: str | None = None
    resource_url: str | None = None


class LearningModuleRead(BaseModel):
    title: str
    week: int
    skill_name: str
    gap_severity: float
    resources: list[LearningResourceRead]
    is_available: bool = False


class LearningPathRead(BaseModel):
    role_name: str
    modules: list[LearningModuleRead]


class TrajectoryRead(BaseModel):
    role_name: str
    fit_score: float
    required_skills: list[str]
    modules: list[LearningModuleRead]


class TrajectoryBootstrapRequest(BaseModel):
    role_name: str | None = None


class TrajectoryBootstrapRead(BaseModel):
    role_name: str
    detected_skills: list[str]
    seeded_skills: list[str]
    skill_request_names: list[str]
    modules: list[LearningModuleRead]
