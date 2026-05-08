from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportRead(BaseModel):
    id: str
    user_id: str
    payload: dict
    created_at: datetime | None = None


class DashboardSummaryRead(BaseModel):
    user_id: str
    readiness_score: float
    role_fit: float
    top_skills: list[str]
    domain_breakdown: dict[str, float] = {}
    pending_hidden_skills: int
    next_event: dict | None = None
    latest_report_id: str | None = None
    latest_report_created_at: datetime | None = None
