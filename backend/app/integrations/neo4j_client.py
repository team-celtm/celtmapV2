from __future__ import annotations

from functools import lru_cache

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config.settings import Settings, get_settings


@lru_cache(maxsize=1)
def get_neo4j_driver(settings: Settings | None = None) -> AsyncDriver | None:
    runtime_settings = settings or get_settings()
    if not runtime_settings.neo4j_uri:
        return None
    return AsyncGraphDatabase.driver(
        runtime_settings.neo4j_uri,
        auth=(runtime_settings.neo4j_user, runtime_settings.neo4j_password),
    )
