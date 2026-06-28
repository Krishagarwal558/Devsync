"""Pydantic schemas for file storage APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FileVersionResponse(BaseModel):
    """Stored file version response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_id: UUID
    workspace_id: UUID
    created_by_device_id: UUID
    content_checksum: str
    size_bytes: int
    storage_key: str
    version_number: int
    created_at: datetime


class StoredFileResponse(BaseModel):
    """Stored file metadata response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    path: str
    file_type: str
    current_version_id: UUID | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FileUploadResponse(BaseModel):
    """Upload response."""

    file_id: UUID
    version_id: UUID
    path: str
    version_number: int
    checksum: str
    size_bytes: int


class StoredFilePage(BaseModel):
    """Paginated file listing."""

    items: list[StoredFileResponse]
    limit: int
    offset: int
    next_offset: int | None


class RestoreFileVersionRequest(BaseModel):
    """Request body for restoring a version."""

    version_id: UUID
    sender_device_id: UUID


class FileDownload:
    """Service-level download DTO."""

    def __init__(self, file_name: str, stream: object, size_bytes: int, checksum: str) -> None:
        """Create download DTO."""
        self.file_name = file_name
        self.stream = stream
        self.size_bytes = size_bytes
        self.checksum = checksum


class UploadFormData(BaseModel):
    """Validated upload form metadata."""

    path: str = Field(min_length=1, max_length=2048)
    sender_device_id: UUID
    checksum: str | None = Field(default=None, max_length=256)
    file_type: str = Field(default="file", min_length=1, max_length=40)

