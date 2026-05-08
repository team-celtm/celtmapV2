from typing import Annotated
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.dependencies.auth import require_admin, require_admin_override
from app.dependencies.services import (
    get_admin_auth_service,
    get_admin_csv_service,
    get_admin_service,
    get_skill_request_service,
)
from app.schemas.mcq import IngestionStatusResponse
from app.schemas.skill_request import SkillRequestAdminOverride, SkillRequestRead
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_csv_service import AdminCSVService
from app.services.admin_service import AdminService
from app.services.skill_request_service import SkillRequestService
from app.tasks.sync import run_celtmind_sync

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def admin_login(
    payload: AdminLoginRequest,
    auth_service: Annotated[AdminAuthService, Depends(get_admin_auth_service)],
) -> dict:
    return await auth_service.login(payload.username, payload.password)


@router.post("/ingest-csv", dependencies=[Depends(require_admin)])
async def ingest_csv(
    file: UploadFile = File(...),
    role_name: str | None = None,
    csv_service: Annotated[AdminCSVService, Depends(get_admin_csv_service)] = None,
) -> dict:
    content = await file.read()
    stats = await csv_service.ingest_questions_from_csv(content, role_name=role_name)
    return {
        "status": "success",
        "stats": stats
    }


@router.post("/sync-celtmind", dependencies=[Depends(require_admin)])
async def sync_celtmind() -> dict:
    task = run_celtmind_sync.delay()
    return {
        "status": "queued",
        "task_id": task.id,
    }


@router.get("/sync-celtmind/status", response_model=IngestionStatusResponse, dependencies=[Depends(require_admin)])
async def get_sync_status(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> dict:
    latest = await admin_service.get_sync_status()
    return {
        "started_at": latest.get("started_at"),
        "completed_at": latest.get("completed_at"),
        "status": latest.get("status", "never_run"),
        "files": latest.get("summary", latest.get("files", [])),
    }


@router.post(
    "/skill-requests/{request_id}/override",
    response_model=SkillRequestRead,
    dependencies=[Depends(require_admin_override)],
)
async def override_skill_request(
    request_id: str,
    payload: SkillRequestAdminOverride,
    skill_request_service: Annotated[SkillRequestService, Depends(get_skill_request_service)],
) -> dict:
    return await skill_request_service.apply_admin_override(
        request_id=request_id,
        decision=payload.decision,
        reason=payload.reason,
    )
