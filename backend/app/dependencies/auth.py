from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import Settings
from app.core.exceptions import UnauthorizedError
from app.dependencies.services import get_app_settings, get_auth_service, get_admin_auth_service
from app.middleware.request_context import update_user_context
from app.schemas.common import AuthenticatedUser
from app.services.auth_service import AuthService
from app.services.admin_auth_service import AdminAuthService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Bearer token is required")
    user = await auth_service.validate_access_token(credentials.credentials)
    request.state.user_id = user.id
    update_user_context(user.id)
    return user


async def require_admin_override(
    settings: Annotated[Settings, Depends(get_app_settings)],
    admin_override_token: Annotated[
        str | None,
        Header(alias="X-Admin-Override-Token"),
    ] = None,
) -> None:
    if not settings.admin_override_token or admin_override_token != settings.admin_override_token:
        raise UnauthorizedError("Valid admin override token is required")


async def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AdminAuthService, Depends(get_admin_auth_service)],
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Admin Bearer token is required")
        
    is_valid = await auth_service.validate_token(credentials.credentials)
    if not is_valid:
        raise UnauthorizedError("Invalid or expired admin token")
