from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_learning_service, get_profile_service, get_skill_service
from app.schemas.common import AuthenticatedUser
from app.schemas.learning import LearningPathRead, LearningResourceRead
from app.services.learning_service import LearningService
from app.services.profile_service import ProfileService
from app.services.skill_service import SkillService

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/path", response_model=LearningPathRead)
async def get_learning_path(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    learning_service: Annotated[LearningService, Depends(get_learning_service)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
    role_name: str | None = Query(default=None),
) -> dict:
    resolved_role = role_name
    if resolved_role is None:
        profile = await profile_service.get_profile(current_user.id, current_user.email)
        resolved_role = profile.get("focus_role")
    if resolved_role is None:
        role_fit = await skill_service.get_role_fit(current_user.id)
        resolved_role = role_fit["role_name"]
    return await learning_service.get_learning_path(current_user.id, resolved_role)


@router.get("/resources", response_model=list[LearningResourceRead])
async def get_learning_resources(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    learning_service: Annotated[LearningService, Depends(get_learning_service)],
    skill_name: str = Query(..., min_length=1),
) -> list[dict]:
    return await learning_service.get_learning_resources(skill_name, user_id=current_user.id)
