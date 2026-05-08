from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from hashlib import sha1

from fastapi import Request

from app.config.settings import Settings
from app.integrations.cache import CacheClient, CacheUnavailableError


@dataclass(slots=True)
class RateLimitResult:
    allowed: bool
    key: str
    limit: int
    remaining: int
    reset_seconds: int
    bucket: str


def _decode_supabase_sub(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        body = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    sub = body.get("sub")
    return str(sub) if sub else None


def _resolve_identity(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        subject = _decode_supabase_sub(token)
        if subject:
            return f"user:{subject}"
        if token:
            return f"token:{sha1(token.encode('utf-8')).hexdigest()}"
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


def _classify_bucket(request: Request, settings: Settings) -> tuple[str, int, int]:
    path = request.url.path
    method = request.method.upper()
    if "/auth/" in path:
        return ("auth", settings.auth_rate_limit, settings.auth_rate_window_seconds)
    ai_segments = (
        "/copilot/",
        "/skills/requests",
        "/written-assessments",
        "/interview/",
    )
    if any(segment in path for segment in ai_segments):
        if method == "GET":
            return ("read", settings.read_rate_limit, settings.read_rate_window_seconds)
        if "/written-assessments" in path and method in {"PATCH", "PUT", "POST"} and not path.endswith("/complete"):
            return ("mutation", settings.mutation_rate_limit, settings.mutation_rate_window_seconds)
        return ("ai", settings.ai_rate_limit, settings.ai_rate_window_seconds)
    if method in {"GET", "HEAD", "OPTIONS"}:
        return ("read", settings.read_rate_limit, settings.read_rate_window_seconds)
    return ("mutation", settings.mutation_rate_limit, settings.mutation_rate_window_seconds)


def enforce_rate_limit(request: Request, settings: Settings, cache: CacheClient) -> RateLimitResult:
    identity = _resolve_identity(request)
    bucket, limit, window_seconds = _classify_bucket(request, settings)
    key = f"rate-limit:{bucket}:{identity}"
    try:
        current = cache.increment(key, window_seconds)
        if bucket == "ai":
            daily_key = f"rate-limit:ai-daily:{identity}"
            daily_count = cache.increment(daily_key, settings.ai_daily_window_seconds)
            if daily_count > settings.ai_daily_limit:
                return RateLimitResult(
                    allowed=False,
                    key=daily_key,
                    limit=settings.ai_daily_limit,
                    remaining=0,
                    reset_seconds=settings.ai_daily_window_seconds,
                    bucket="ai-daily",
                )
    except CacheUnavailableError:
        if not settings.redis_fail_open_enabled:
            raise
        return RateLimitResult(
            allowed=True,
            key=key,
            limit=limit,
            remaining=limit,
            reset_seconds=window_seconds,
            bucket=bucket,
        )
    remaining = max(limit - current, 0)
    return RateLimitResult(
        allowed=current <= limit,
        key=key,
        limit=limit,
        remaining=remaining,
        reset_seconds=window_seconds,
        bucket=bucket,
    )
