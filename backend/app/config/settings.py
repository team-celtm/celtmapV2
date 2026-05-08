from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "CELTM Backend"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    api_v1_prefix: str = "/api/v1"
    api_compat_prefix: str = "/api"
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_secret_key: str = Field(default="", alias="SUPABASE_SECRET_KEY")
    supabase_legacy_key: str = Field(default="", alias="SUPABASE_KEY")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_publishable_key: str = Field(default="", alias="SUPABASE_PUBLISHABLE_KEY")

    neo4j_uri: str = Field(default="", alias="NEO4J_URI")
    neo4j_user: str = Field(default="", alias="NEO4J_USER")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="OPENAI_EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_enabled: bool = Field(default=True, alias="REDIS_ENABLED")
    redis_fail_open: bool = Field(default=False, alias="REDIS_FAIL_OPEN")
    redis_socket_connect_timeout_seconds: float = Field(
        default=0.2,
        alias="REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS",
    )
    redis_socket_timeout_seconds: float = Field(
        default=0.2,
        alias="REDIS_SOCKET_TIMEOUT_SECONDS",
    )
    redis_health_check_interval_seconds: int = Field(
        default=30,
        alias="REDIS_HEALTH_CHECK_INTERVAL_SECONDS",
    )
    dead_letter_queue_name: str = Field(default="celtm:dead-letter", alias="DEAD_LETTER_QUEUE_NAME")

    celtmind_dir: Path = Field(default=Path("../CELTMIND"), alias="CELTMIND_DIR")
    celtmind_sync_enabled: bool = Field(default=True, alias="CELTMIND_SYNC_ENABLED")
    profile_bucket: str = Field(default="profile-assets", alias="PROFILE_BUCKET")
    artifact_bucket: str = Field(default="career-artifacts", alias="ARTIFACT_BUCKET")

    default_page_limit: int = 25
    max_page_limit: int = 100

    rag_top_k: int = Field(default=6, alias="RAG_TOP_K")
    rag_cache_ttl_seconds: int = Field(default=300, alias="RAG_CACHE_TTL_SECONDS")
    rag_user_memory_limit: int = Field(default=120, alias="RAG_USER_MEMORY_LIMIT")
    rag_user_memory_archive_after_days: int = Field(
        default=45,
        alias="RAG_USER_MEMORY_ARCHIVE_AFTER_DAYS",
    )
    transcript_timeout_seconds: int = Field(default=45, alias="TRANSCRIPT_TIMEOUT_SECONDS")

    auth_rate_limit: int = Field(default=10, alias="AUTH_RATE_LIMIT")
    auth_rate_window_seconds: int = Field(default=300, alias="AUTH_RATE_WINDOW_SECONDS")
    read_rate_limit: int = Field(default=120, alias="READ_RATE_LIMIT")
    read_rate_window_seconds: int = Field(default=60, alias="READ_RATE_WINDOW_SECONDS")
    mutation_rate_limit: int = Field(default=30, alias="MUTATION_RATE_LIMIT")
    mutation_rate_window_seconds: int = Field(default=60, alias="MUTATION_RATE_WINDOW_SECONDS")
    ai_rate_limit: int = Field(default=5, alias="AI_RATE_LIMIT")
    ai_rate_window_seconds: int = Field(default=60, alias="AI_RATE_WINDOW_SECONDS")
    ai_daily_limit: int = Field(default=50, alias="AI_DAILY_LIMIT")
    ai_daily_window_seconds: int = Field(default=86400, alias="AI_DAILY_WINDOW_SECONDS")

    admin_override_token: str = Field(default="", alias="ADMIN_OVERRIDE_TOKEN")
    admin_user: str = Field(default="admin@celtm.com", alias="ADMIN_USER")
    admin_pass: str = Field(default="admin123", alias="ADMIN_PASS")
    admin_gateway_code: str = Field(default="CELTM2026", alias="ADMIN_GATEWAY_CODE")

    celery_broker_url: str | None = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend: str | None = Field(default=None, alias="CELERY_RESULT_BACKEND")
    celery_eager_mode: bool = Field(default=False, alias="CELERY_EAGER_MODE")

    @property
    def broker_url(self) -> str:
        if self.celery_eager_mode:
            return "memory://"
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        if self.celery_eager_mode:
            return "cache+memory://"
        return self.celery_result_backend or self.redis_url

    @property
    def redis_fail_open_enabled(self) -> bool:
        return self.redis_fail_open or self.app_env.lower() == "development"

    @property
    def celtmind_path(self) -> Path:
        base_dir = Path(__file__).resolve().parents[2]
        path = self.celtmind_dir
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return path

    @property
    def can_sync_celtmind(self) -> bool:
        return self.celtmind_sync_enabled and self.celtmind_path.exists()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def resolved_supabase_service_role_key(self) -> str:
        return (
            self.supabase_service_role_key or self.supabase_secret_key or self.supabase_legacy_key
        )

    @property
    def resolved_supabase_anon_key(self) -> str:
        return self.supabase_anon_key or self.supabase_publishable_key

    def require_supabase(self) -> None:
        if not self.supabase_url or not self.resolved_supabase_service_role_key:
            raise ValueError(
                "SUPABASE_URL and a Supabase service key "
                "(SUPABASE_SERVICE_ROLE_KEY, SUPABASE_SECRET_KEY, or SUPABASE_KEY) "
                "must be configured"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
