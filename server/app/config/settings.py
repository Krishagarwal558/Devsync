"""Application settings for DevSync Cloud."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DEVSYNC_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "DevSync Cloud"
    app_version: str = "0.2.0b1"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    database_url: str = "postgresql+asyncpg://devsync:devsync@localhost:5432/devsync"
    jwt_secret_key: SecretStr = Field(
        default=SecretStr("devsync-development-secret-change-before-production"),
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    bcrypt_rounds: int = 12
    storage_root: str = "server/storage"
    max_upload_bytes: int = 50 * 1024 * 1024
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:8000", "http://localhost:8000"])
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        """Limit environment names to known deployment modes."""
        normalized = value.lower()
        allowed = {"development", "test", "alpha", "beta", "production"}
        if normalized not in allowed:
            raise ValueError(f"DEVSYNC_ENVIRONMENT must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        """Validate the HTTP port."""
        if value < 1 or value > 65535:
            raise ValueError("DEVSYNC_PORT must be between 1 and 65535")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Ensure the configured database URL uses SQLAlchemy async PostgreSQL."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DEVSYNC_DATABASE_URL must start with postgresql+asyncpg://")
        return value

    @field_validator("access_token_minutes")
    @classmethod
    def validate_access_lifetime(cls, value: int) -> int:
        """Keep access tokens short-lived."""
        if value < 1 or value > 60:
            raise ValueError("DEVSYNC_ACCESS_TOKEN_MINUTES must be between 1 and 60")
        return value

    @field_validator("refresh_token_days")
    @classmethod
    def validate_refresh_lifetime(cls, value: int) -> int:
        """Keep refresh token lifetime bounded."""
        if value < 1 or value > 90:
            raise ValueError("DEVSYNC_REFRESH_TOKEN_DAYS must be between 1 and 90")
        return value

    @field_validator("max_upload_bytes")
    @classmethod
    def validate_max_upload_bytes(cls, value: int) -> int:
        """Keep upload size bounded."""
        if value < 1 or value > 1024 * 1024 * 1024:
            raise ValueError("DEVSYNC_MAX_UPLOAD_BYTES must be between 1 byte and 1 GiB")
        return value

    @field_validator("rate_limit_requests")
    @classmethod
    def validate_rate_limit_requests(cls, value: int) -> int:
        """Validate request limit."""
        if value < 1 or value > 10000:
            raise ValueError("DEVSYNC_RATE_LIMIT_REQUESTS must be between 1 and 10000")
        return value

    @field_validator("rate_limit_window_seconds")
    @classmethod
    def validate_rate_limit_window(cls, value: int) -> int:
        """Validate rate limit window."""
        if value < 1 or value > 3600:
            raise ValueError("DEVSYNC_RATE_LIMIT_WINDOW_SECONDS must be between 1 and 3600")
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Reject unsafe production defaults."""
        internet_facing = self.environment.lower() in {"beta", "production"}
        if internet_facing:
            if self.jwt_secret_key.get_secret_value() == "devsync-development-secret-change-before-production":
                raise ValueError("DEVSYNC_JWT_SECRET_KEY must be changed for beta/production")
            if self.jwt_secret_key.get_secret_value() == "replace-this-with-at-least-32-random-characters":
                raise ValueError("DEVSYNC_JWT_SECRET_KEY must not use the example value for beta/production")
            if "*" in self.cors_allowed_origins:
                raise ValueError("Wildcard CORS origins are not allowed in beta/production")
            if self.reload:
                raise ValueError("DEVSYNC_RELOAD must be false in beta/production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
