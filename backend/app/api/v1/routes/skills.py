from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_skill_service
from app.schemas.common import AuthenticatedUser
from app.schemas.skill import HiddenSkillCandidateRead, RoleFitRead, SkillGapRead, SkillRead
from app.services.skill_service import SkillService

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/me", response_model=list[SkillRead])
async def get_my_skills(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
) -> list[dict]:
    return await skill_service.list_user_skills(current_user.id)


@router.get("/me/role-fit", response_model=RoleFitRead)
async def get_role_fit(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
) -> dict:
    return await skill_service.get_role_fit(current_user.id)


@router.get("/me/gaps", response_model=list[SkillGapRead])
async def get_skill_gaps(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
) -> list[dict]:
    return await skill_service.get_skill_gaps(current_user.id)


@router.get("/me/hidden", response_model=list[HiddenSkillCandidateRead])
async def get_hidden_candidates(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
) -> list[dict]:
    return await skill_service.list_hidden_candidates(current_user.id)


@router.post("/me/hidden/{candidate_id}/approve", response_model=HiddenSkillCandidateRead | None)
async def approve_hidden_candidate(
    candidate_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
) -> dict | None:
    return await skill_service.approve_hidden_candidate(current_user.id, candidate_id)


@router.post("/me/hidden/{candidate_id}/reject", response_model=HiddenSkillCandidateRead | None)
async def reject_hidden_candidate(
    candidate_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
) -> dict | None:
    return await skill_service.reject_hidden_candidate(current_user.id, candidate_id)
