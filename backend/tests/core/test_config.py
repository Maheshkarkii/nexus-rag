"""Tests for backend configuration, environment modes, and URL generation."""

from app.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Verify default configuration values adhere to development standards."""
    settings = get_settings()
    assert settings.APP_NAME == "AI Research Assistant"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.BACKEND_PORT == 8000
    assert len(settings.BACKEND_CORS_ORIGINS) > 0
    assert settings.is_development is True
    assert settings.is_production is False


def test_cors_origins_parsing() -> None:
    """Verify that CORS origins can parse comma-separated strings, JSON arrays, and lists."""
    test_str = "http://localhost:3000,http://example.com"
    parsed = Settings.assemble_cors_origins(test_str)
    assert "http://localhost:3000" in parsed
    assert "http://example.com" in parsed

    test_json = '["http://site-a.com", "http://site-b.com"]'
    parsed_json = Settings.assemble_cors_origins(test_json)
    assert "http://site-a.com" in parsed_json
    assert "http://site-b.com" in parsed_json


def test_database_url_generation() -> None:
    """Verify async and sync database URL construction when DATABASE_URL is not set."""
    settings = Settings(
        DATABASE_URL="",
        POSTGRES_SERVER="postgres-host",
        POSTGRES_PORT=5432,
        POSTGRES_DB="test_db",
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
    )
    assert settings.async_database_url == "postgresql+asyncpg://test_user:test_password@postgres-host:5432/test_db"
    assert settings.sync_database_url == "postgresql://test_user:test_password@postgres-host:5432/test_db"
