from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_profile_service
from app.schemas.common import AuthenticatedUser
from app.schemas.profile import ArtifactRead, ProfileRead, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])
required_file = File(...)
resume_form = Form(default="resume")


@router.get("/me", response_model=ProfileRead)
async def read_profile(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    return await profile_service.get_profile(current_user.id, current_user.email, current_user.full_name)


@router.patch("/me", response_model=ProfileRead)
async def update_profile(
    payload: ProfileUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    return await profile_service.update_profile(
        current_user.id,
        payload.model_dump(exclude_none=True),
    )


@router.post("/me/avatar", response_model=ProfileRead)
async def upload_avatar(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    file: UploadFile = required_file,
) -> dict:
    return await profile_service.upload_avatar(current_user.id, file, "profile-assets")


@router.post("/me/artifacts", response_model=ArtifactRead)
async def upload_artifact(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    file: UploadFile = required_file,
    file_type: str = resume_form,
) -> dict:
    return await profile_service.upload_artifact(
        user_id=current_user.id,
        upload=file,
        bucket_name="career-artifacts",
        file_type=file_type,
    )


@router.get("/me/artifacts", response_model=list[ArtifactRead])
async def list_artifacts(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[dict]:
    return await profile_service.list_artifacts(current_user.id)


@router.delete("/me/artifacts/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    success = await profile_service.delete_artifact(current_user.id, artifact_id)
    return {"status": "success" if success else "failed"}

@router.put("/me/artifacts/{artifact_id}", response_model=ArtifactRead)
async def replace_artifact(
    artifact_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    file: UploadFile = required_file,
) -> dict:
    return await profile_service.replace_artifact(
        user_id=current_user.id,
        artifact_id=artifact_id,
        upload=file,
    )
