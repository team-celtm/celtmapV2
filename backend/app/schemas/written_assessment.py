from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WrittenAssessmentCreateRequest(BaseModel):
    skill_id: str | None = Field(default=None, max_length=160)
    skill_request_id: str | None = None
    prompt: str | None = Field(default=None, max_length=12000)
    evaluator_mode: Literal["teacher", "liberal_ai", "strict_ai"] = "teacher"


class WrittenAssessmentSubmissionUpdate(BaseModel):
    submission_text: str = Field(min_length=20, max_length=50000)
    evaluator_mode: Literal["teacher", "liberal_ai", "strict_ai"] | None = None


class WrittenAssessmentRead(BaseModel):
    id: str
    user_id: str
    skill_id: str | None = None
    skill_request_id: str | None = None
    prompt: str
    rubric: dict[str, Any] = Field(default_factory=dict)
    submission_text: str | None = None
    score: float | None = None
    feedback: str | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
