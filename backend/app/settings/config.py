"""Backend configuration management."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendSettings:
    """Runtime configuration for the backend service."""

    app_name: str
    environment: str
    token_secret: str
    token_issuer: str
    database_url: str
    log_level: str

    @classmethod
    def from_environment(cls) -> "BackendSettings":
        """Load settings from environment variables."""
        return cls(
            app_name=os.getenv("DEVSYNC_APP_NAME", "DevSync"),
            environment=os.getenv("DEVSYNC_ENVIRONMENT", "development"),
            token_secret=os.getenv("DEVSYNC_TOKEN_SECRET", "devsync-local-development-secret"),
            token_issuer=os.getenv("DEVSYNC_TOKEN_ISSUER", "devsync"),
            database_url=os.getenv("DEVSYNC_DATABASE_URL", "sqlite:///devsync-backend.sqlite"),
            log_level=os.getenv("DEVSYNC_LOG_LEVEL", "INFO"),
        )

