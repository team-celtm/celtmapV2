from __future__ import annotations

from strenum import StrEnum


class AssessmentStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class InterviewSessionStatus(StrEnum):
    DRAFT = "draft"
    TRANSCRIPT_READY = "transcript_ready"
    PROCESSING = "processing"
    COMPLETED = "completed"


class HiddenSkillStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DomainEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DomainEventType(StrEnum):
    CELTMIND_SYNCED = "celtmind.synced"
    ASSESSMENT_COMPLETED = "assessment.completed"
    INTERVIEW_COMPLETED = "interview.completed"
    HIDDEN_SKILL_APPROVED = "hidden_skill.approved"
    ARTIFACT_UPLOADED = "artifact.uploaded"
    DASHBOARD_REFRESH_REQUESTED = "dashboard.refresh_requested"
    SKILL_MEASURED = "skill.measured"
