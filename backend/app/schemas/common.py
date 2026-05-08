from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str


class CursorParams(BaseModel):
    cursor: str | None = None
    limit: int = Field(default=25, ge=1, le=100)


class PageInfo(BaseModel):
    next_cursor: str | None = None
    limit: int


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    page_info: PageInfo


class HealthResponse(BaseModel):
    status: str
    services: dict[str, bool]
    timestamp: datetime


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None = None
    role: str | None = None
    full_name: str | None = None
    raw_claims: dict[str, Any] = Field(default_factory=dict)
