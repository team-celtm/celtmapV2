from __future__ import annotations

from pydantic import BaseModel, Field


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1)
    page_context: str | None = None


class CopilotSourceRead(BaseModel):
    tag: str
    title: str
    detail: str


class CopilotChatResponse(BaseModel):
    answer: str
    confidence: float
    sources: list[CopilotSourceRead]
