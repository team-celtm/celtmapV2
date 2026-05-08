from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.config.settings import get_settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_written_assessment_service
from app.schemas.common import AuthenticatedUser
from app.schemas.written_assessment import (
    WrittenAssessmentCreateRequest,
    WrittenAssessmentRead,
    WrittenAssessmentSubmissionUpdate,
)
from app.services.written_assessment_service import WrittenAssessmentService
from app.tasks.written_assessments import (
    evaluate_written_assessment,
    run_written_assessment_evaluation,
)

router = APIRouter(prefix="/written-assessments", tags=["written-assessments"])


@router.get("", response_model=list[WrittenAssessmentRead])
async def list_written_assessments(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    written_assessment_service: Annotated[
        WrittenAssessmentService, Depends(get_written_assessment_service)
    ],
) -> list[dict]:
    return await written_assessment_service.list_sessions(current_user.id)


@router.post("", response_model=WrittenAssessmentRead)
async def create_written_assessment(
    payload: WrittenAssessmentCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    written_assessment_service: Annotated[
        WrittenAssessmentService, Depends(get_written_assessment_service)
    ],
) -> dict:
    return await written_assessment_service.create_session(
        user_id=current_user.id,
        skill_id=payload.skill_id,
        skill_request_id=payload.skill_request_id,
        prompt=payload.prompt,
        evaluator_mode=payload.evaluator_mode,
    )


@router.get("/{session_id}", response_model=WrittenAssessmentRead)
async def get_written_assessment(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    written_assessment_service: Annotated[
        WrittenAssessmentService, Depends(get_written_assessment_service)
    ],
) -> dict:
    session = await written_assessment_service.get_session_for_user(current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Written assessment not found")
    return session


@router.patch("/{session_id}", response_model=WrittenAssessmentRead)
async def update_written_assessment_submission(
    session_id: str,
    payload: WrittenAssessmentSubmissionUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    written_assessment_service: Annotated[
        WrittenAssessmentService, Depends(get_written_assessment_service)
    ],
) -> dict:
    session = await written_assessment_service.save_submission(
        user_id=current_user.id,
        session_id=session_id,
        submission_text=payload.submission_text,
        evaluator_mode=payload.evaluator_mode,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Written assessment not found")
    return session


@router.post("/{session_id}/complete", response_model=WrittenAssessmentRead)
async def complete_written_assessment(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    written_assessment_service: Annotated[
        WrittenAssessmentService, Depends(get_written_assessment_service)
    ],
) -> dict:
    session = await written_assessment_service.mark_processing(
        user_id=current_user.id,
        session_id=session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Written assessment not found")
    if get_settings().celery_eager_mode:
        await run_written_assessment_evaluation(
            session_id=session_id,
            user_id=current_user.id,
        )
    else:
        evaluate_written_assessment.delay(session_id, current_user.id)
    latest_session = await written_assessment_service.get_session_for_user(
        current_user.id,
        session_id,
    )
    return latest_session or session
