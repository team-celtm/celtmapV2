from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AssessmentStatus


class AssessmentCreateRequest(BaseModel):
    category: str = "general"
    assessment_type: str = "mcq"
    question_type: str = "MCQ"
    skill_id: str | None = None
    skill_request_id: str | None = None


class AssessmentRead(BaseModel):
    id: str
    user_id: str
    category: str
    assessment_type: str = "mcq"
    question_type: str = "MCQ"
    skill_id: str | None = None
    skill_request_id: str | None = None
    score: float | None = None
    status: AssessmentStatus
    created_at: datetime | None = None
    completed_at: datetime | None = None


class AssessmentAnswerInput(BaseModel):
    question_id: str
    selected_option_id: str | None = None
    answer_text: str | None = None

    @model_validator(mode="after")
    def validate_answer_payload(self) -> AssessmentAnswerInput:
        if self.selected_option_id or (self.answer_text and self.answer_text.strip()):
            return self
        raise ValueError("Either selected_option_id or answer_text is required.")


class AssessmentAnswerBatch(BaseModel):
    answers: list[AssessmentAnswerInput]


class AssessmentCompletionResponse(BaseModel):
    assessment_id: str
    score: float
    correct_answers: int
    total_questions: int
    status: AssessmentStatus
    detailed_feedback: dict | None = None


class AssessmentLogEntry(BaseModel):
    id: str
    type: str  # mcq, situational, written, interview
    subject: str
    score: float | None = None
    status: str
    completed_at: datetime | None = None
    insight: str | None = None
    feedback: str | None = None
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    plagiarism: dict[str, object] | None = None
    readiness_score: float | None = None
    role_name: str | None = None


class SubjectDetail(BaseModel):
    key: str
    title: str
    description: str
    source: str
    severity: float
    current_score: float | None = None
    skill_id: str | None = None
    skill_request_id: str | None = None
    resource_count: int = 0
