"""Desktop synchronization state models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Authenticated user profile stored locally."""

    id: UUID
    email: str
    display_name: str


class WorkspaceBinding(BaseModel):
    """Local folder attached to a cloud workspace."""

    workspace_id: UUID
    workspace_name: str
    local_folder_path: Path
    last_sequence: int = 0


class KnownFile(BaseModel):
    """Known local checksum for a workspace path."""

    workspace_id: UUID
    path: str
    checksum: str
    file_id: UUID | None = None
    version_id: UUID | None = None
    updated_at: datetime


class ActivityEntry(BaseModel):
    """Recent local activity entry."""

    message: str
    created_at: datetime

