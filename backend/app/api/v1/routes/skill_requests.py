from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_skill_request_service
from app.schemas.common import AuthenticatedUser
from app.schemas.skill_request import SkillRequestCreate, SkillRequestRead
from app.services.skill_request_service import SkillRequestService

router = APIRouter(prefix="/skills/requests", tags=["skill-requests"])


@router.get("", response_model=list[SkillRequestRead])
async def list_skill_requests(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_request_service: Annotated[SkillRequestService, Depends(get_skill_request_service)],
) -> list[dict]:
    return await skill_request_service.list_requests(current_user.id)


@router.post("", response_model=SkillRequestRead)
async def create_skill_request(
    payload: SkillRequestCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_request_service: Annotated[SkillRequestService, Depends(get_skill_request_service)],
) -> dict:
    return await skill_request_service.create_request(
        user_id=current_user.id,
        requested_name=payload.requested_name,
        requested_type=payload.requested_type,
        description=payload.description,
        strict_bank_match=True,
    )


@router.get("/{request_id}", response_model=SkillRequestRead)
async def get_skill_request(
    request_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_request_service: Annotated[SkillRequestService, Depends(get_skill_request_service)],
) -> dict:
    request = await skill_request_service.get_request_for_user(current_user.id, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Skill request not found")
    return request
