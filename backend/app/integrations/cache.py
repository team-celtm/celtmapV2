from __future__ import annotations

import json
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.config.settings import Settings


class CacheUnavailableError(RuntimeError):
    pass


class CacheClient:
    def __init__(self, settings: Settings) -> None:
        self._client: Redis | None = None
        if settings.redis_enabled and settings.redis_url:
            self._client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
                socket_timeout=settings.redis_socket_timeout_seconds,
                health_check_interval=settings.redis_health_check_interval_seconds,
                retry_on_timeout=False,
            )

    def _require_client(self) -> Redis:
        if self._client is None:
            raise CacheUnavailableError("Redis is disabled for this runtime")
        return self._client

    def get_json(self, key: str) -> Any | None:
        if self._client is None:
            return None
        try:
            payload = self._client.get(key)
            if payload is None:
                return None
            return json.loads(str(payload))
        except RedisError:
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        if self._client is None:
            return
        try:
            self._client.set(key, json.dumps(value), ex=ttl_seconds)
        except RedisError:
            return

    def increment(self, key: str, ttl_seconds: int) -> int:
        client = self._require_client()
        try:
            pipeline = client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, ttl_seconds, nx=True)
            count, _ = pipeline.execute()
            return int(count)
        except RedisError as exc:
            raise CacheUnavailableError("Redis increment failed") from exc

    def list_length(self, key: str) -> int:
        if self._client is None:
            return 0
        try:
            return int(self._client.llen(key))
        except RedisError:
            return 0

    def push_dead_letter(self, key: str, payload: dict[str, Any]) -> None:
        if self._client is None:
            return
        try:
            self._client.lpush(key, json.dumps(payload))
        except RedisError:
            return

    def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except RedisError:
            return False
