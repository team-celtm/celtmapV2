from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_trajectory_service
from app.schemas.common import AuthenticatedUser
from app.schemas.learning import (
    TrajectoryBootstrapRead,
    TrajectoryBootstrapRequest,
    TrajectoryRead,
)
from app.services.trajectory_service import TrajectoryService

router = APIRouter(prefix="/trajectory", tags=["trajectory"])


@router.post("/bootstrap", response_model=TrajectoryBootstrapRead)
async def bootstrap_trajectory(
    payload: TrajectoryBootstrapRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    trajectory_service: Annotated[TrajectoryService, Depends(get_trajectory_service)],
) -> dict:
    return await trajectory_service.bootstrap_user_path(
        current_user.id,
        role_name=payload.role_name,
    )


@router.get("/{role_name}", response_model=TrajectoryRead)
async def get_trajectory(
    role_name: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    trajectory_service: Annotated[TrajectoryService, Depends(get_trajectory_service)],
) -> dict:
    return await trajectory_service.get_trajectory(current_user.id, role_name)


@router.get("/me/alternates", response_model=list[TrajectoryRead])
async def get_alternate_roles(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    trajectory_service: Annotated[TrajectoryService, Depends(get_trajectory_service)],
) -> list[dict]:
    return await trajectory_service.get_alternate_roles(current_user.id)
