"""Pydantic schemas for synchronization events."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SyncEventType(StrEnum):
    """Supported synchronization event types."""

    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    FOLDER_CREATED = "folder_created"
    FOLDER_DELETED = "folder_deleted"
    RENAME = "rename"
    MOVE = "move"
    METADATA_CHANGED = "metadata_changed"


class SyncEventPayload(BaseModel):
    """Extensible event payload metadata."""

    modified_at: datetime | None = None
    file_size: int | None = Field(default=None, ge=0)
    source_path: str | None = Field(default=None, min_length=1, max_length=2048)
    target_path: str | None = Field(default=None, min_length=1, max_length=2048)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("source_path", "target_path")
    @classmethod
    def trim_optional_path(cls, value: str | None) -> str | None:
        """Trim optional path fields."""
        if value is None:
            return None
        cleaned = value.strip().replace("\\", "/")
        return cleaned or None


class CreateSyncEventRequest(BaseModel):
    """Request body for submitting a synchronization event."""

    sender_device_id: UUID
    event_type: SyncEventType
    path: str = Field(min_length=1, max_length=2048)
    payload: SyncEventPayload = Field(default_factory=SyncEventPayload)
    checksum: str | None = Field(default=None, max_length=256)
    bandwidth_bytes: int = Field(default=0, ge=0)

    @field_validator("path")
    @classmethod
    def trim_path(cls, value: str) -> str:
        """Normalize path separators before service validation."""
        cleaned = value.strip().replace("\\", "/")
        if not cleaned:
            raise ValueError("Path is required")
        return cleaned

    @field_validator("checksum")
    @classmethod
    def trim_checksum(cls, value: str | None) -> str | None:
        """Trim optional checksum."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "CreateSyncEventRequest":
        """Validate event-specific payload requirements."""
        if self.event_type in {SyncEventType.RENAME, SyncEventType.MOVE} and not self.payload.target_path:
            raise ValueError("Rename and move events require payload.target_path")
        return self


class SyncEventResponse(BaseModel):
    """Synchronization event response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    sender_device_id: UUID
    sequence: int
    event_type: str
    path: str
    payload: dict[str, object]
    checksum: str | None
    bandwidth_bytes: int
    status: str
    created_at: datetime


class SyncEventPage(BaseModel):
    """Paginated synchronization event response."""

    items: list[SyncEventResponse]
    limit: int
    offset: int
    next_offset: int | None


class ReplaySyncEventsResponse(BaseModel):
    """Replay response after a client-provided sequence."""

    after_sequence: int
    items: list[SyncEventResponse]
    next_after_sequence: int | None


class AcknowledgeSyncEventsRequest(BaseModel):
    """Request body for acknowledging processed events."""

    device_id: UUID
    event_ids: list[UUID] | None = Field(default=None, max_length=500)
    up_to_sequence: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_ack_selector(self) -> "AcknowledgeSyncEventsRequest":
        """Require exactly one acknowledgement selector."""
        has_event_ids = self.event_ids is not None and len(self.event_ids) > 0
        has_up_to_sequence = self.up_to_sequence is not None
        if has_event_ids == has_up_to_sequence:
            raise ValueError("Provide either event_ids or up_to_sequence")
        return self


class AcknowledgeSyncEventsResponse(BaseModel):
    """Acknowledgement response."""

    acknowledged_count: int

