from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import app.main as main_module


class AllowedRateLimit:
    allowed = True
    limit = 999
    remaining = 998
    reset_seconds = 1
    bucket = "test"


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_DEBUG", "false")
    main_module.get_settings.cache_clear()
    monkeypatch.setattr(
        main_module,
        "enforce_rate_limit",
        lambda request, settings, cache: AllowedRateLimit(),
    )
    app = main_module.create_application()
    return TestClient(app, raise_server_exceptions=False)


def test_request_middleware_returns_499_for_cancelled_requests(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    @client.app.get("/cancel-test")
    async def cancel_test() -> None:
        raise asyncio.CancelledError()

    response = client.get("/cancel-test")

    assert response.status_code == 499
    assert response.headers["X-Request-ID"]
    assert response.headers["X-RateLimit-Limit"] == "999"
    assert response.headers["X-RateLimit-Remaining"] == "998"


def test_request_middleware_preserves_real_runtime_errors(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    @client.app.get("/runtime-error-test")
    async def runtime_error_test() -> None:
        raise RuntimeError("boom")

    response = client.get("/runtime-error-test")

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "internal_server_error",
        "message": "Internal server error",
    }
