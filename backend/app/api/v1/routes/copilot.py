from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_rag_service
from app.schemas.common import AuthenticatedUser
from app.schemas.copilot import CopilotChatRequest, CopilotChatResponse
from app.services.rag_service import RagService

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat", response_model=CopilotChatResponse)
async def chat_with_copilot(
    payload: CopilotChatRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
) -> dict:
    return await rag_service.build_copilot_reply(
        user_id=current_user.id,
        page_context=payload.page_context,
        message=payload.message,
    )
