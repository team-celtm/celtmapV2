from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from app.core.exceptions import NotFoundError

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_mcq_service
from app.schemas.assessment import (
    AssessmentAnswerBatch,
    AssessmentCompletionResponse,
    AssessmentCreateRequest,
    AssessmentLogEntry,
    AssessmentRead,
)
from app.schemas.common import AuthenticatedUser
from app.services.mcq_service import MCQService

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("/log", response_model=list[AssessmentLogEntry])
async def get_assessment_log(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> list:
    return await mcq_service.get_assessment_log(user_id=current_user.id)


@router.get("/subjects")
async def list_discoverable_subjects(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> list:
    return await mcq_service.get_discoverable_subjects(user_id=current_user.id)


@router.get("/subjects/{subject_key}")
async def get_subject_detail(
    subject_key: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> dict:
    return await mcq_service.get_subject_detail(user_id=current_user.id, subject_key=subject_key)



@router.post("", response_model=AssessmentRead)
async def create_assessment(
    payload: AssessmentCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> dict:
    return await mcq_service.create_assessment(
        user_id=current_user.id,
        category=payload.category,
        assessment_type=payload.assessment_type,
        question_type=payload.question_type,
        skill_id=payload.skill_id,
        skill_request_id=payload.skill_request_id,
    )


@router.post("/{assessment_id}/answers")
async def submit_assessment_answers(
    assessment_id: str,
    payload: AssessmentAnswerBatch,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> dict:
    answers = await mcq_service.submit_answers(
        assessment_id=assessment_id,
        user_id=current_user.id,
        answers=[item.model_dump() for item in payload.answers],
    )
    return {
        "assessment_id": assessment_id, 
        "answers_recorded": len(answers),
        "results": answers
    }

@router.post("/{assessment_id}/complete", response_model=AssessmentCompletionResponse)
async def complete_assessment(
    assessment_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> dict:
    return await mcq_service.complete_assessment(
        assessment_id=assessment_id,
        user_id=current_user.id,
    )
