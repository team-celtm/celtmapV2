from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_interview_service
from app.schemas.common import AuthenticatedUser
from app.schemas.interview import (
    InterviewResultRead,
    InterviewSessionCreateRequest,
    InterviewSessionRead,
    MediaReferenceSubmission,
    TranscriptSubmission,
)
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post("/sessions", response_model=InterviewSessionRead)
async def create_session(
    payload: InterviewSessionCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
) -> dict:
    return await interview_service.create_session(
        user_id=current_user.id,
        role_name=payload.role_name,
        skill_request_id=payload.skill_request_id,
        interview_type=payload.interview_type,
    )


@router.get("/sessions", response_model=list[InterviewSessionRead])
async def list_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[dict]:
    return await interview_service.list_sessions(current_user.id, limit=limit, cursor=cursor)


@router.post("/sessions/{session_id}/transcript", response_model=InterviewSessionRead)
async def submit_transcript(
    session_id: str,
    payload: TranscriptSubmission,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
) -> dict:
    return await interview_service.submit_transcript(session_id, payload.transcript)


@router.post("/sessions/{session_id}/media", response_model=InterviewSessionRead)
async def submit_media_reference(
    session_id: str,
    payload: MediaReferenceSubmission,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
) -> dict:
    return await interview_service.submit_media_reference(session_id, payload.media_reference)


@router.post("/sessions/{session_id}/complete", response_model=InterviewSessionRead)
async def complete_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
) -> dict:
    return await interview_service.complete_session(session_id=session_id, user_id=current_user.id)


@router.get("/sessions/{session_id}/results", response_model=InterviewResultRead | None)
async def get_session_results(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
) -> dict | None:
    return await interview_service.get_result(session_id)
