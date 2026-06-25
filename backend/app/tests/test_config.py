"""Tests for application configuration."""

from app.core.config import Settings, get_settings


def test_settings_defaults():
    """Settings loads with sensible defaults."""
    settings = Settings()
    assert settings.app_name == "Smart WiFi Dashboard"
    assert settings.port == 8000
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_expiry_minutes == 30
    assert settings.redis_cache_ttl == 10
    assert settings.db_pool_size == 20
    assert settings.router_max_connections_per_tenant == 5
    assert settings.circuit_breaker_failure_threshold == 5
    assert settings.anomaly_baseline_days == 7
    assert settings.report_max_period_days == 30


def test_settings_database_url():
    """Database URL defaults to local PostgreSQL."""
    settings = Settings()
    assert "postgresql+asyncpg" in settings.database_url
    assert "smartwifi" in settings.database_url


def test_settings_redis_url():
    """Redis URL defaults to local Redis."""
    settings = Settings()
    assert "redis://localhost" in settings.redis_url


def test_get_settings_cached():
    """get_settings returns the same cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
