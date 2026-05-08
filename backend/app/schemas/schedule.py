from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ScheduleEventCreate(BaseModel):
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    event_type: str
    metadata: dict[str, str] = {}


class ScheduleEventRead(BaseModel):
    id: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    event_type: str
    metadata: dict[str, str] = {}


class ScheduleEventUpdate(BaseModel):
    title: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    event_type: str | None = None
    metadata: dict[str, str] | None = None
