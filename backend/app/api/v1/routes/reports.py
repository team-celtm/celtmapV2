from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_projection_service, get_report_service
from app.schemas.common import AuthenticatedUser
from app.schemas.reports import ReportRead
from app.services.projection_service import ProjectionService
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/me/latest", response_model=ReportRead | None)
async def get_latest_report(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> dict | None:
    return await report_service.get_latest_report(current_user.id)


@router.post("/me/generate", response_model=ReportRead)
async def generate_report(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
    projection_service: Annotated[ProjectionService, Depends(get_projection_service)],
) -> dict:
    report = await report_service.generate_report(current_user.id)
    await projection_service.refresh_dashboard_projection(current_user.id)
    return report


@router.get("/me/passport.pdf")
async def export_skill_passport(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> Response:
    file_name, payload = await report_service.render_skill_passport_pdf(current_user.id)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
