from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies.auth import get_current_user
from app.dependencies.services import (
    get_mcq_service,
    get_profile_service,
    get_trajectory_service,
)
from app.schemas.common import AuthenticatedUser
from app.services.mcq_service import MCQService
from app.services.profile_service import ProfileService
from app.services.trajectory_service import TrajectoryService

router = APIRouter(prefix="/placement", tags=["placement"])


class PlacementAnswer(BaseModel):
    question_id: str
    selected_option_id: str | None = None


class PlacementSubmitRequest(BaseModel):
    answers: list[PlacementAnswer]
    role_name: str | None = None


# ---------------------------------------------------------------------------
# 1. GET /placement/status  →  { has_completed_placement: bool }
# ---------------------------------------------------------------------------


@router.get("/status")
async def placement_status(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    completed = await mcq_service.get_placement_status(
        user_id=current_user.id,
        profile_service=profile_service,
    )
    return {"has_completed_placement": completed}


# ---------------------------------------------------------------------------
# 2. GET /placement/questions  →  list of 2-4 generalised MCQ questions
# ---------------------------------------------------------------------------


@router.get("/questions")
async def placement_questions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
    role_name: str | None = None,
) -> dict:
    questions = await mcq_service.get_placement_questions(role_name=role_name)
    return {"questions": questions, "count": len(questions)}



# ---------------------------------------------------------------------------
# 3. POST /placement/submit  →  score + domain breakdown
# ---------------------------------------------------------------------------


@router.post("/submit")
async def placement_submit(
    payload: PlacementSubmitRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    trajectory_service: Annotated[TrajectoryService, Depends(get_trajectory_service)],
) -> dict:
    result = await mcq_service.complete_placement_assessment(
        user_id=current_user.id,
        answers=[a.model_dump() for a in payload.answers],
        role_name=payload.role_name,
        profile_service=profile_service,
    )
    if result.get("status") == "completed":
        try:
            bootstrap = await trajectory_service.bootstrap_user_path(
                current_user.id,
                role_name=payload.role_name,
            )
            result["generated_subjects"] = [
                module["skill_name"] for module in bootstrap.get("modules", [])
            ]
        except Exception as e:
            import logging
            logging.error(f"Failed to bootstrap user path: {e}")
            result["generated_subjects"] = []
    return result
