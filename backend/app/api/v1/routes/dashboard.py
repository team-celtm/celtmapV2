from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_dashboard_service
from app.schemas.common import AuthenticatedUser
from app.schemas.reports import DashboardSummaryRead
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryRead)
async def get_dashboard_summary(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    refresh: bool = False,
) -> dict:
    return await dashboard_service.get_summary(current_user.id, refresh=refresh)
