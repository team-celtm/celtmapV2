from __future__ import annotations

from app.config.settings import Settings


def test_settings_accepts_legacy_supabase_secret_key() -> None:
    settings = Settings(
        _env_file=None,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="secret-key",
    )

    assert settings.resolved_supabase_service_role_key == "secret-key"
    settings.require_supabase()


def test_settings_accepts_legacy_supabase_key() -> None:
    settings = Settings(
        _env_file=None,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_KEY="legacy-key",
    )

    assert settings.resolved_supabase_service_role_key == "legacy-key"
    settings.require_supabase()


def test_settings_falls_back_to_publishable_key_for_anon_key() -> None:
    settings = Settings(
        _env_file=None,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="publishable-key",
    )

    assert settings.resolved_supabase_anon_key == "publishable-key"
