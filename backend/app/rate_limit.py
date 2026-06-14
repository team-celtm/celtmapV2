from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.settings import Settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    backend: str
    error: str | None = None
    status_code: int = 429


class RateLimiter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._memory_state: dict[str, tuple[int, float]] = {}
        self._redis_client: Any | None = None
        self._redis_error: str | None = None

    @property
    def backend_name(self) -> str:
        backend = self.settings.rate_limit_backend.strip().lower()
        if backend == "redis" and self.settings.redis_url:
            return "redis"
        return "memory"

    @property
    def bucket_count(self) -> int:
        return len(self._memory_state)

    @property
    def redis_error(self) -> str | None:
        return self._redis_error

    async def check_many(self, checks: list[tuple[str, str, int, int]]) -> RateLimitDecision:
        decisions: list[RateLimitDecision] = []
        for bucket, identity, limit, window_seconds in checks:
            decision = await self.check(bucket, identity, limit, window_seconds)
            decisions.append(decision)
            if not decision.allowed:
                return decision
        active = decisions[-1] if decisions else RateLimitDecision(True, 0, 0, 0, self.backend_name)
        if not decisions:
            return active
        remaining = min(decision.remaining for decision in decisions if decision.limit > 0)
        retry_after = max(decision.retry_after for decision in decisions)
        limit = min(decision.limit for decision in decisions if decision.limit > 0)
        return RateLimitDecision(True, limit, remaining, retry_after, active.backend)

    async def check(self, bucket: str, identity: str, limit: int, window_seconds: int) -> RateLimitDecision:
        if limit <= 0:
            return RateLimitDecision(True, 0, 0, 0, self.backend_name)
        if self.backend_name == "redis":
            try:
                return await self._check_redis(bucket, identity, limit, window_seconds)
            except Exception as exc:
                self._redis_error = str(exc)[:200]
                if self.settings.is_hosted_mode:
                    return RateLimitDecision(
                        False,
                        limit,
                        0,
                        30,
                        "redis",
                        error="Shared rate limiter is unavailable",
                        status_code=503,
                    )
        return self._check_memory(bucket, identity, limit, window_seconds)

    def _check_memory(self, bucket: str, identity: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.time()
        key = f"{bucket}:{identity}"
        count, reset_at = self._memory_state.get(key, (0, now + window_seconds))
        if reset_at <= now:
            count, reset_at = 0, now + window_seconds
        count += 1
        self._memory_state[key] = (count, reset_at)
        if len(self._memory_state) > 10_000:
            expired_keys = [item_key for item_key, (_, item_reset) in self._memory_state.items() if item_reset <= now]
            for item_key in expired_keys[:2_000]:
                self._memory_state.pop(item_key, None)
        remaining = max(0, limit - count)
        retry_after = max(0, int(reset_at - now))
        return RateLimitDecision(count <= limit, limit, remaining, retry_after, "memory")

    async def _check_redis(self, bucket: str, identity: str, limit: int, window_seconds: int) -> RateLimitDecision:
        client = await self._get_redis_client()
        key = f"celtm:rate:{bucket}:{identity}"
        count = int(await client.incr(key))
        if count == 1:
            await client.expire(key, window_seconds)
        ttl = int(await client.ttl(key))
        retry_after = max(0, ttl if ttl >= 0 else window_seconds)
        remaining = max(0, limit - count)
        self._redis_error = None
        return RateLimitDecision(count <= limit, limit, remaining, retry_after, "redis")

    async def _get_redis_client(self) -> Any:
        if self._redis_client is not None:
            return self._redis_client
        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise RuntimeError("redis package is required for RATE_LIMIT_BACKEND=redis") from exc
        self._redis_client = redis.from_url(
            self.settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        await self._redis_client.ping()
        return self._redis_client
