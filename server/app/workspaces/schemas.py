"""Pydantic schemas for workspace management."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateWorkspaceRequest(BaseModel):
    """Request body for creating a workspace."""

    name: str = Field(min_length=1, max_length=160)
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        """Normalize workspace names."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Workspace name is required")
        return cleaned


class UpdateWorkspaceRequest(BaseModel):
    """Request body for updating workspace metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=160)
    settings: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        """Normalize optional workspace names."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Workspace name is required")
        return cleaned


class WorkspaceMemberResponse(BaseModel):
    """Workspace membership response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class WorkspaceResponse(BaseModel):
    """Workspace response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    slug: str
    status: str
    settings: dict[str, Any]
    archived_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkspaceDetailResponse(WorkspaceResponse):
    """Workspace detail response with current user's membership."""

    membership: WorkspaceMemberResponse

