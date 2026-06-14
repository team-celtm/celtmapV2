from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "CELTM Phase 1 API"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    api_v1_prefix: str = "/api/v1"
    frontend_origin: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        alias="FRONTEND_ORIGIN",
    )

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_publishable_key: str = Field(default="", alias="SUPABASE_PUBLISHABLE_KEY")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_secret_key: str = Field(default="", alias="SUPABASE_SECRET_KEY")
    supabase_legacy_key: str = Field(default="", alias="SUPABASE_KEY")
    database_url: str = Field(default="", alias="DATABASE_URL")
    supabase_database_url: str = Field(default="", alias="SUPABASE_DATABASE_URL")
    supabase_db_connection_string: str = Field(default="", alias="SUPABASE_DB_CONNECTION_STRING")
    postgres_schema: str = Field(default="celtm_app", alias="CELTM_POSTGRES_SCHEMA")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    allow_heuristic_ai_fallbacks: bool = Field(default=False, alias="ALLOW_HEURISTIC_AI_FALLBACKS")

    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    supabase_storage_bucket: str = Field(default="celtm-private-uploads", alias="SUPABASE_STORAGE_BUCKET")
    supabase_storage_create_bucket: bool = Field(default=False, alias="SUPABASE_STORAGE_CREATE_BUCKET")
    signed_url_ttl_seconds: int = Field(default=900, alias="SIGNED_URL_TTL_SECONDS")
    allow_local_file_serving: bool = Field(default=True, alias="ALLOW_LOCAL_FILE_SERVING")

    max_avatar_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_AVATAR_UPLOAD_BYTES")
    max_resume_upload_bytes: int = Field(default=10 * 1024 * 1024, alias="MAX_RESUME_UPLOAD_BYTES")
    max_artifact_upload_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_ARTIFACT_UPLOAD_BYTES")
    max_csv_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_CSV_UPLOAD_BYTES")
    max_extracted_text_chars: int = Field(default=120_000, alias="MAX_EXTRACTED_TEXT_CHARS")

    profile_link_max_bytes: int = Field(default=512 * 1024, alias="PROFILE_LINK_MAX_BYTES")
    profile_link_timeout_seconds: float = Field(default=8.0, alias="PROFILE_LINK_TIMEOUT_SECONDS")
    profile_link_max_redirects: int = Field(default=3, alias="PROFILE_LINK_MAX_REDIRECTS")

    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_backend: str = Field(default="memory", alias="RATE_LIMIT_BACKEND")
    redis_url: str = Field(default="", alias="REDIS_URL")
    rate_limit_general_per_minute: int = Field(default=600, alias="RATE_LIMIT_GENERAL_PER_MINUTE")
    rate_limit_admin_login_per_15m: int = Field(default=5, alias="RATE_LIMIT_ADMIN_LOGIN_PER_15M")
    rate_limit_uploads_per_hour: int = Field(default=30, alias="RATE_LIMIT_UPLOADS_PER_HOUR")
    rate_limit_ai_per_hour: int = Field(default=30, alias="RATE_LIMIT_AI_PER_HOUR")
    rate_limit_ai_global_per_minute: int = Field(default=120, alias="RATE_LIMIT_AI_GLOBAL_PER_MINUTE")
    rate_limit_assessment_per_minute: int = Field(default=180, alias="RATE_LIMIT_ASSESSMENT_PER_MINUTE")

    openai_timeout_seconds: float = Field(default=35.0, alias="OPENAI_TIMEOUT_SECONDS")
    ai_cache_enabled: bool = Field(default=True, alias="AI_CACHE_ENABLED")
    ai_cache_ttl_seconds: int = Field(default=86_400, alias="AI_CACHE_TTL_SECONDS")
    ai_cache_max_entries: int = Field(default=2_000, alias="AI_CACHE_MAX_ENTRIES")
    async_ai_jobs_enabled: bool = Field(default=False, alias="ASYNC_AI_JOBS_ENABLED")

    upload_scan_enabled: bool = Field(default=False, alias="UPLOAD_SCAN_ENABLED")
    clamav_tcp_host: str = Field(default="", alias="CLAMAV_TCP_HOST")
    clamav_tcp_port: int = Field(default=3310, alias="CLAMAV_TCP_PORT")
    clamav_timeout_seconds: float = Field(default=8.0, alias="CLAMAV_TIMEOUT_SECONDS")
    fail_closed_upload_scan: bool = Field(default=True, alias="FAIL_CLOSED_UPLOAD_SCAN")

    admin_mfa_required: bool = Field(default=False, alias="ADMIN_MFA_REQUIRED")
    admin_mfa_secret: str = Field(default="", alias="ADMIN_MFA_SECRET")
    monitoring_token: str = Field(default="", alias="MONITORING_TOKEN")

    admin_user: str = Field(default="admin@celtm.com", alias="ADMIN_USER")
    admin_pass: str = Field(default="admin123", alias="ADMIN_PASS")
    admin_gateway_code: str = Field(default="CELTM2026", alias="ADMIN_GATEWAY_CODE")
    jwt_secret: str = Field(default="", alias="CELTM_JWT_SECRET")
    data_dir: Path = Field(default=BASE_DIR / "data", alias="CELTM_DATA_DIR")

    @property
    def is_hosted_mode(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod", "hosted"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def effective_storage_backend(self) -> str:
        return self.storage_backend.strip().lower() or "local"

    @property
    def local_file_serving_enabled(self) -> bool:
        return bool(self.allow_local_file_serving and not self.is_hosted_mode)

    @property
    def supabase_api_key(self) -> str:
        return (
            self.supabase_anon_key
            or self.supabase_publishable_key
            or self.supabase_service_role_key
            or self.supabase_secret_key
            or self.supabase_legacy_key
        )

    @property
    def resolved_jwt_secret(self) -> str:
        return (
            self.jwt_secret
            or self.supabase_service_role_key
            or self.supabase_secret_key
            or self.admin_pass
            or "celtm-phase1-local-secret"
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "celtm_phase1.sqlite3"

    @property
    def database_target(self) -> str | Path:
        return (
            self.database_url
            or self.supabase_database_url
            or self.supabase_db_connection_string
            or self.database_path
        )

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    def validate_hosted_security(self) -> None:
        if not self.is_hosted_mode:
            return

        missing = [
            name
            for name, value in {
                "FRONTEND_ORIGIN": self.frontend_origin,
                "SUPABASE_URL": self.supabase_url,
                "SUPABASE_ANON_KEY or SUPABASE_PUBLISHABLE_KEY": self.supabase_anon_key or self.supabase_publishable_key,
                "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key or self.supabase_secret_key,
                "DATABASE_URL or SUPABASE_DATABASE_URL": self.database_url or self.supabase_database_url or self.supabase_db_connection_string,
                "CELTM_JWT_SECRET": self.jwt_secret,
                "ADMIN_USER": self.admin_user,
                "ADMIN_PASS": self.admin_pass,
                "ADMIN_GATEWAY_CODE": self.admin_gateway_code,
                "SUPABASE_STORAGE_BUCKET": self.supabase_storage_bucket,
                "MONITORING_TOKEN": self.monitoring_token,
            }.items()
            if not str(value or "").strip()
        ]
        if missing:
            raise RuntimeError(f"Hosted CELTM configuration is missing: {', '.join(missing)}")

        # Hosted validation intentionally compares against the local development defaults.
        weak_values = {
            "ADMIN_USER": self.admin_user == "admin@celtm.com",
            "ADMIN_PASS": self.admin_pass == ("admin" + "123"),
            "ADMIN_GATEWAY_CODE": self.admin_gateway_code == "CELTM2026",
            "CELTM_JWT_SECRET": self.jwt_secret in {"", "celtm-phase1-local-secret"},
        }
        weak = [name for name, is_weak in weak_values.items() if is_weak]
        if weak:
            raise RuntimeError(f"Hosted CELTM configuration uses default or weak credentials: {', '.join(weak)}")

        local_origins = {"http://127.0.0.1:3000", "http://localhost:3000"}
        if any(origin in local_origins for origin in self.cors_origins):
            raise RuntimeError("Hosted CELTM FRONTEND_ORIGIN must not include localhost origins.")

        if self.effective_storage_backend != "supabase":
            raise RuntimeError("Hosted CELTM STORAGE_BACKEND must be 'supabase' so uploads are private.")

        if self.allow_local_file_serving:
            raise RuntimeError("Hosted CELTM must set ALLOW_LOCAL_FILE_SERVING=false.")

        if not (self.database_url or self.supabase_database_url or self.supabase_db_connection_string):
            raise RuntimeError("Hosted CELTM must use Postgres through DATABASE_URL or SUPABASE_DATABASE_URL.")

        if self.admin_mfa_required and not self.admin_mfa_secret:
            raise RuntimeError("Hosted CELTM ADMIN_MFA_REQUIRED=true requires ADMIN_MFA_SECRET.")

        rate_limit_backend = self.rate_limit_backend.strip().lower()
        if rate_limit_backend not in {"memory", "redis"}:
            raise RuntimeError("Hosted CELTM RATE_LIMIT_BACKEND must be 'memory' or 'redis'.")

        if rate_limit_backend == "redis" and not self.redis_url:
            raise RuntimeError("Hosted CELTM RATE_LIMIT_BACKEND=redis requires REDIS_URL.")

        if self.upload_scan_enabled and not self.clamav_tcp_host:
            raise RuntimeError("Hosted CELTM UPLOAD_SCAN_ENABLED=true requires CLAMAV_TCP_HOST.")

        if self.signed_url_ttl_seconds < 60 or self.signed_url_ttl_seconds > 3600:
            raise RuntimeError("Hosted CELTM SIGNED_URL_TTL_SECONDS must be between 60 and 3600.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_hosted_security()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
