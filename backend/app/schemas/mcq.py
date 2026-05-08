from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MCQOptionPublic(BaseModel):
    id: str
    option_text: str


class MCQQuestionPublic(BaseModel):
    id: str
    question_text: str
    category: str
    difficulty: str
    skill_id: str | None = None
    skill_request_id: str | None = None
    question_type: str = "MCQ"
    scenario: str | None = None
    options: list[MCQOptionPublic]


class MCQQuestionBatchResponse(BaseModel):
    questions: list[MCQQuestionPublic]
    count: int


class MCQQuestionRequest(BaseModel):
    category: str | None = None
    difficulty: str | None = None
    skill_id: str | None = None
    skill_request_id: str | None = None
    question_type: str = "MCQ"
    limit: int = Field(default=10, ge=1, le=50)


class IngestionSummary(BaseModel):
    file_name: str
    checksum: str
    inserted_questions: int
    updated_questions: int
    skipped_rows: int


class IngestionStatusResponse(BaseModel):
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: str
    files: list[IngestionSummary]
