from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.routes._pagination import build_cursor_page
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_interview_service
from app.schemas.common import AuthenticatedUser
from app.services.interview_service import InterviewService

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
async def list_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    interview_service: Annotated[InterviewService, Depends(get_interview_service)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    items = await interview_service.list_sessions(current_user.id, limit=limit, cursor=cursor)
    return build_cursor_page(items, limit)
