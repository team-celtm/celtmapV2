from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from app.config.settings import Settings


class EvaluationProvider(Protocol):
    async def evaluate(self, prompt: str) -> dict[str, Any]: ...


def _ensure_json_output_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    if any("json" in message.get("content", "").lower() for message in messages):
        return messages

    return [
        {
            "role": "system",
            "content": "Respond with valid JSON only. Do not wrap the JSON in markdown.",
        },
        *messages,
    ]


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = bool(settings.openai_api_key)
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            timeout=90.0,
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def evaluate(self, prompt: str) -> dict[str, Any]:
        if not self._enabled:
            return {"mode": "heuristic", "content": prompt}
        result = await self.chat_json(
            messages=[{"role": "user", "content": prompt}],
            model=self._settings.openai_chat_model,
        )
        return result["data"]

    async def chat_text(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if not self._enabled:
            fallback = messages[-1]["content"] if messages else ""
            return {
                "text": fallback,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "model": "heuristic",
            }
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": model or self._settings.openai_chat_model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        return {
            "text": message,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            "model": payload.get("model", model or self._settings.openai_chat_model),
        }

    async def chat_json(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if not self._enabled:
            prompt = messages[-1]["content"] if messages else ""
            return {
                "data": {"mode": "heuristic", "content": prompt},
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "model": "heuristic",
            }
        json_messages = _ensure_json_output_messages(messages)
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": model or self._settings.openai_chat_model,
                "messages": json_messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        return {
            "data": json.loads(content),
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            "model": payload.get("model", model or self._settings.openai_chat_model),
        }

    async def embed_texts(self, texts: list[str]) -> dict[str, Any]:
        if not self._enabled:
            zero_vector = [0.0] * self._settings.embedding_dimensions
            return {
                "embeddings": [zero_vector for _ in texts],
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "model": "heuristic",
            }
        response = await self._client.post(
            "/embeddings",
            json={
                "model": self._settings.openai_embedding_model,
                "input": texts,
            },
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        return {
            "embeddings": [item["embedding"] for item in payload.get("data", [])],
            "usage": {
                "input_tokens": usage.get("prompt_tokens", usage.get("total_tokens", 0)),
                "output_tokens": 0,
            },
            "model": payload.get("model", self._settings.openai_embedding_model),
        }

    async def close(self) -> None:
        await self._client.aclose()
