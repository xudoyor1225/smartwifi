"""Application configuration using Pydantic Settings.

Loads configuration from environment variables with sensible defaults
for local development. All sensitive values should be provided via
environment variables or a .env file in production.

Supports horizontal scaling (Req 13.8) by externalizing all state
configuration (database, Redis, Celery broker) so multiple instances
can share the same backing services.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or a .env file.
    Variable names are case-insensitive and map directly to field names.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Smart WiFi Dashboard"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database (SQLite for local dev, PostgreSQL for production)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost/smartwifi"
    database_url_sync: str = "postgresql://postgres:postgres@localhost/smartwifi"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Redis (cache, sessions, pub/sub)
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 10  # seconds - max staleness for cached data (Req 13.6)
    redis_session_ttl: int = 1800  # 30 minutes - JWT session duration (Req 1.5)

    # Celery (async task processing)
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # JWT Authentication
    jwt_secret_key: str = "change-me-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 30

    # Rate Limiting (Req 1.6, 1.7)
    rate_limit_max_attempts: int = 5
    rate_limit_window_seconds: int = 600  # 10 minutes
    brute_force_max_attempts: int = 20
    brute_force_window_seconds: int = 3600  # 1 hour
    brute_force_block_seconds: int = 1800  # 30 minutes

    # MikroTik Router (Req 13.3, 13.4, 13.5)
    router_connection_timeout: int = 5  # seconds
    router_request_timeout: int = 10  # seconds
    router_max_connections_per_tenant: int = 5
    router_connection_queue_timeout: int = 10  # seconds

    # Encryption (AES-256-GCM for router passwords - Req 9.4)
    encryption_key: str = "change-me-encryption-key-32bytes!"

    # Circuit Breaker (Req 12.4, 12.5)
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_failure_window: int = 60  # seconds
    circuit_breaker_recovery_timeout: int = 30  # seconds

    # AI / Traffic Analysis (Req 7.1, 7.5, 7.7)
    netflow_collection_interval: int = 60  # seconds
    anomaly_baseline_days: int = 7
    anomaly_threshold_std: float = 3.0

    # Reports (Req 8.4, 8.6, 8.9)
    report_max_retention_hours: int = 24
    report_max_per_admin: int = 50
    report_max_period_days: int = 30


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings instance.

    Uses lru_cache to ensure settings are loaded once and reused
    across the application lifecycle. Thread-safe for concurrent access.
    """
    return Settings()
