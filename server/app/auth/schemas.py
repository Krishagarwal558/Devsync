"""Pydantic schemas for authentication."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        """Normalize display names."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name is required")
        return cleaned


class LoginRequest(BaseModel):
    """Request body for login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    """Request body for refresh token rotation."""

    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    """Request body for logout."""

    refresh_token: str = Field(min_length=32, max_length=512)


class UserResponse(BaseModel):
    """Public user response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class AuthResponse(BaseModel):
    """Response returned after login/register/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

