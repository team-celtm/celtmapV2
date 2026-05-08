from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.v1.routes._pagination import build_cursor_page
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_schedule_service
from app.schemas.common import AuthenticatedUser
from app.schemas.schedule import ScheduleEventCreate, ScheduleEventRead, ScheduleEventUpdate
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/events", response_model=ScheduleEventRead)
async def create_event(
    payload: ScheduleEventCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    schedule_service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict:
    return await schedule_service.create_event(current_user.id, payload.model_dump(mode="json"))


@router.get("/events")
async def list_events(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    schedule_service: Annotated[ScheduleService, Depends(get_schedule_service)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    items = await schedule_service.list_events(current_user.id, limit=limit, cursor=cursor)
    return build_cursor_page(items, limit)


@router.patch("/events/{event_id}", response_model=ScheduleEventRead)
async def update_event(
    event_id: str,
    payload: ScheduleEventUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    schedule_service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict:
    updated = await schedule_service.update_event(
        current_user.id,
        event_id,
        payload.model_dump(mode="json"),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Schedule event not found")
    return updated


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    schedule_service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> Response:
    deleted = await schedule_service.delete_event(current_user.id, event_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Schedule event not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
