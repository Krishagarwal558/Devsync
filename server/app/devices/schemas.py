"""Pydantic schemas for device management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterDeviceRequest(BaseModel):
    """Request body for registering a device."""

    name: str = Field(min_length=1, max_length=120)
    platform: str = Field(min_length=1, max_length=80)
    public_key: str | None = Field(default=None, max_length=4096)

    @field_validator("name", "platform")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        """Trim required text fields."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value is required")
        return cleaned

    @field_validator("public_key")
    @classmethod
    def clean_public_key(cls, value: str | None) -> str | None:
        """Trim optional public key."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class UpdateDeviceRequest(BaseModel):
    """Request body for renaming/updating a device."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    platform: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("name", "platform")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        """Trim optional text fields."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value is required")
        return cleaned


class DeviceResponse(BaseModel):
    """Device response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    platform: str
    public_key: str | None
    trust_status: str
    last_seen_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

