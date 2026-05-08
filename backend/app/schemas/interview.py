from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import InterviewSessionStatus


class InterviewSessionCreateRequest(BaseModel):
    role_name: str | None = None
    skill_request_id: str | None = None
    interview_type: str = "role"


class TranscriptSubmission(BaseModel):
    transcript: str


class MediaReferenceSubmission(BaseModel):
    media_reference: str


class CompatibilityInterviewStartRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("role_name", "roleName"),
    )
    skill_request_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("skill_request_id", "skillRequestId"),
    )
    interview_type: str = Field(
        default="role",
        validation_alias=AliasChoices("interview_type", "interviewType"),
    )


class CompatibilityInterviewSubmission(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("session_id", "sessionId"),
    )
    role_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("role_name", "roleName"),
    )
    skill_request_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("skill_request_id", "skillRequestId"),
    )
    interview_type: str = Field(
        default="role",
        validation_alias=AliasChoices("interview_type", "interviewType"),
    )
    transcript: str | None = None
    media_reference: str | None = Field(
        default=None,
        validation_alias=AliasChoices("media_reference", "mediaReference"),
    )


class InterviewSessionRead(BaseModel):
    id: str
    user_id: str
    role_name: str | None = None
    skill_request_id: str | None = None
    interview_type: str = "role"
    status: InterviewSessionStatus
    transcript: str | None = None
    created_at: datetime | None = None


class TranscriptTurnRead(BaseModel):
    question_id: str | None = None
    question_text: str | None = None
    source_document: dict | None = None
    answer_id: str | None = None
    answer_text: str | None = None
    evaluation_metrics: dict[str, float] = Field(default_factory=dict)
    evidence: str | None = None
    created_at: datetime | None = None


class InterviewResultRead(BaseModel):
    session_id: str
    score: float
    feedback: str
    detected_skills: list[dict[str, str | float]]
    hidden_skills: list[dict[str, str | float]]
    evaluation_metrics: dict[str, float] = Field(default_factory=dict)
    transcript_turns: list[TranscriptTurnRead] = Field(default_factory=list)
