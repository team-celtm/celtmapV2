from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_settings_service
from app.schemas.common import AuthenticatedUser
from app.schemas.profile import SecuritySettingsUpdate, UserPreferenceRead, UserPreferenceUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/me", response_model=UserPreferenceRead)
async def get_settings(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict:
    return await settings_service.get_settings(current_user.id)


@router.patch("/me", response_model=UserPreferenceRead)
async def patch_settings(
    payload: UserPreferenceUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict:
    return await settings_service.update_settings(
        current_user.id,
        payload.model_dump(exclude_none=True),
    )


@router.patch("/me/notifications", response_model=UserPreferenceRead)
async def patch_notifications(
    payload: UserPreferenceUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict:
    notification_payload = payload.model_dump(
        exclude_none=True,
        include={"desktop_notifications", "weekly_digest", "folio_reminders", "folio_focus"},
    )
    return await settings_service.update_settings(current_user.id, notification_payload)


@router.get("/me/security", response_model=UserPreferenceRead)
async def get_security_settings(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict:
    return await settings_service.get_settings(current_user.id)


@router.patch("/me/security", response_model=UserPreferenceRead)
async def patch_security_settings(
    payload: SecuritySettingsUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict:
    return await settings_service.update_settings(
        current_user.id,
        payload.model_dump(exclude_none=True),
    )
