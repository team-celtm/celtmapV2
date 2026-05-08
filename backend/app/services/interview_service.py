from __future__ import annotations

from datetime import datetime, timezone

from app.models.enums import DomainEventType, InterviewSessionStatus
from app.repositories.interview_repository import InterviewRepository
from app.services.domain_event_service import DomainEventService


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository,
        event_service: DomainEventService,
    ) -> None:
        self.repository = repository
        self.event_service = event_service

    async def create_session(
        self,
        *,
        user_id: str,
        role_name: str | None,
        skill_request_id: str | None = None,
        interview_type: str = "role",
    ) -> dict:
        return await self.repository.create_session(
            {
                "user_id": user_id,
                "role_name": role_name,
                "skill_request_id": skill_request_id,
                "interview_type": interview_type,
                "status": InterviewSessionStatus.DRAFT.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def submit_transcript(self, session_id: str, transcript: str) -> dict:
        return await self.repository.update_session(
            session_id,
            {
                "transcript": transcript,
                "status": InterviewSessionStatus.TRANSCRIPT_READY.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def submit_media_reference(self, session_id: str, media_reference: str) -> dict:
        return await self.repository.update_session(
            session_id,
            {
                "media_reference": media_reference,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def complete_session(self, *, session_id: str, user_id: str) -> dict:
        session = await self.repository.update_session(
            session_id,
            {
                "status": InterviewSessionStatus.PROCESSING.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await self.event_service.emit(
            event_type=DomainEventType.INTERVIEW_COMPLETED,
            aggregate_type="interview_session",
            aggregate_id=session_id,
            payload={"user_id": user_id},
        )
        return session

    async def get_result(self, session_id: str) -> dict | None:
        session = await self.repository.get_session(session_id)
        evaluation = await self.repository.get_latest_evaluation(session_id)
        if session is None or evaluation is None:
            return None
        transcript_turns = await self.repository.get_session_turns(session_id)
        return {
            "session_id": session_id,
            "score": evaluation["score"],
            "feedback": evaluation["feedback"],
            "detected_skills": evaluation.get("detected_skills", []),
            "hidden_skills": evaluation.get("hidden_skills", []),
            "evaluation_metrics": evaluation.get("metrics", {}),
            "transcript_turns": transcript_turns,
        }

    async def list_sessions(self, user_id: str, limit: int, cursor: str | None) -> list[dict]:
        return await self.repository.list_sessions(user_id=user_id, limit=limit, cursor=cursor)
