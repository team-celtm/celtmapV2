from __future__ import annotations

from functools import lru_cache

import httpx
from supabase import Client, ClientOptions, create_client

from app.config.settings import Settings, get_settings


@lru_cache(maxsize=1)
def _build_supabase_client(supabase_url: str, service_role_key: str) -> Client:
    # We explicitly disable HTTP/2 here because we've seen intermittent
    # `httpx.RemoteProtocolError: <ConnectionTerminated ... PROTOCOL_ERROR>`
    # from PostgREST/Supabase on some Windows + local network setups.
    # A bounded timeout also prevents long-hanging requests from blocking the UI.
    httpx_client = httpx.Client(
        http2=False,
        timeout=httpx.Timeout(20.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    options = ClientOptions(
        httpx_client=httpx_client,
        postgrest_client_timeout=httpx.Timeout(20.0),
    )
    return create_client(
        supabase_url,
        service_role_key,
        options,
    )


def get_supabase_client(settings: Settings | None = None) -> Client:
    runtime_settings = settings or get_settings()
    runtime_settings.require_supabase()
    return _build_supabase_client(
        runtime_settings.supabase_url,
        runtime_settings.resolved_supabase_service_role_key,
    )
