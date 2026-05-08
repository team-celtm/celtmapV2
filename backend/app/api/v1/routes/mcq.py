from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_mcq_service
from app.schemas.common import AuthenticatedUser
from app.schemas.mcq import MCQQuestionBatchResponse
from app.services.mcq_service import MCQService

router = APIRouter(prefix="/mcq", tags=["mcq"])


@router.get("/questions", response_model=MCQQuestionBatchResponse)
async def get_questions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
    category: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    skill_id: str | None = Query(default=None),
    skill_request_id: str | None = Query(default=None),
    question_type: str = Query(default="MCQ"),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    questions = await mcq_service.get_questions(
        category=category,
        difficulty=difficulty,
        skill_id=skill_id,
        skill_request_id=skill_request_id,
        question_type=question_type,
        limit=limit,
    )
    return {"questions": questions, "count": len(questions)}
