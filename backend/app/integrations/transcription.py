from __future__ import annotations

from typing import Protocol

from app.config.settings import Settings


class TranscriptionProvider(Protocol):
    async def transcribe_reference(self, media_reference: str) -> str: ...


class PlaceholderTranscriptionProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def transcribe_reference(self, media_reference: str) -> str:
        return (
            "Transcription provider not configured. "
            f"Store media reference for later processing: {media_reference}"
        )
