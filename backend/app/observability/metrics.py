from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from statistics import mean
from threading import Lock


class InMemoryMetrics:
    def __init__(self) -> None:
        self._request_latencies: deque[float] = deque(maxlen=500)
        self._route_latencies: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=200))
        self._request_count = 0
        self._error_count = 0
        self._rate_limited_count = 0
        self._worker_failures = 0
        self._last_worker_heartbeat: datetime | None = None
        self._lock = Lock()

    def record_request(self, route: str, latency_ms: float, status_code: int) -> None:
        with self._lock:
            self._request_count += 1
            self._request_latencies.append(latency_ms)
            self._route_latencies[route].append(latency_ms)
            if status_code >= 500:
                self._error_count += 1

    def record_rate_limited(self) -> None:
        with self._lock:
            self._rate_limited_count += 1

    def record_worker_failure(self) -> None:
        with self._lock:
            self._worker_failures += 1

    def heartbeat_worker(self) -> None:
        with self._lock:
            self._last_worker_heartbeat = datetime.now(timezone.utc)

    def snapshot(self) -> dict:
        with self._lock:
            route_stats = {
                route: round(mean(latencies), 2)
                for route, latencies in self._route_latencies.items()
                if latencies
            }
            return {
                "request_count": self._request_count,
                "error_count": self._error_count,
                "rate_limited_count": self._rate_limited_count,
                "worker_failures": self._worker_failures,
                "latency_ms_avg": round(mean(self._request_latencies), 2)
                if self._request_latencies
                else 0.0,
                "latency_ms_by_route": route_stats,
                "last_worker_heartbeat": self._last_worker_heartbeat.isoformat()
                if self._last_worker_heartbeat
                else None,
            }


metrics = InMemoryMetrics()
