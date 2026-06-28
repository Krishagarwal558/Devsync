"""WebSocket message schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ClientEventType(StrEnum):
    """Client-to-server WebSocket event types."""

    WORKSPACE_JOIN = "workspace_join"
    WORKSPACE_LEAVE = "workspace_leave"
    DEVICE_HEARTBEAT = "device_heartbeat"
    SYNC_ACK = "sync_ack"


class WorkspaceJoinMessage(BaseModel):
    """Join a workspace room."""

    type: ClientEventType
    workspace_id: UUID
    device_id: UUID
    last_sequence: int = Field(default=0, ge=0)


class WorkspaceLeaveMessage(BaseModel):
    """Leave a workspace room."""

    type: ClientEventType
    workspace_id: UUID


class DeviceHeartbeatMessage(BaseModel):
    """Device heartbeat over WebSocket."""

    type: ClientEventType
    workspace_id: UUID
    device_id: UUID


class SyncAckMessage(BaseModel):
    """Acknowledge sync events up to a sequence."""

    type: ClientEventType
    workspace_id: UUID
    sequence: int = Field(ge=1)


class WebSocketError(BaseModel):
    """Consistent WebSocket error message."""

    type: str = "error"
    code: str
    message: str


class WorkspaceJoinedEvent(BaseModel):
    """Server event emitted after joining a workspace."""

    type: str = "workspace_joined"
    workspace_id: UUID
    replayed_events: int


class DeviceConnectedEvent(BaseModel):
    """Server presence event for a connected device."""

    type: str = "device_connected"
    workspace_id: UUID
    device_id: UUID
    device_name: str


class DeviceDisconnectedEvent(BaseModel):
    """Server presence event for a disconnected device."""

    type: str = "device_disconnected"
    workspace_id: UUID
    device_id: UUID


class SyncEventMessage(BaseModel):
    """Server sync event message."""

    type: str = "sync_event"
    workspace_id: UUID
    sequence: int
    event_type: str
    path: str
    payload: dict[str, object]
    checksum: str | None
    size_bytes: int | None = None
    created_at: datetime

