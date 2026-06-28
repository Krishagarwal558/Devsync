"""Desktop client settings models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ClientSettings(BaseModel):
    """User-configurable desktop client settings."""

    server_url: str = Field(default="http://127.0.0.1:8000")
    user_data_dir: Path = Field(default_factory=lambda: Path.home() / ".devsync")
    state_path: Path = Field(default_factory=lambda: Path.home() / ".devsync" / "desktop_state.sqlite")
    logs_dir: Path = Field(default_factory=lambda: Path.home() / ".devsync" / "logs")
    debounce_seconds: float = 1.0
    remote_apply_seconds: float = 3.0
