"""Realtime protocol names shared by backend and desktop clients."""

from __future__ import annotations

from enum import StrEnum


class ClientEventType(StrEnum):
    """Events that clients may send over WebSocket connections."""

    WORKSPACE_JOIN = "workspace_join"
    WORKSPACE_LEAVE = "workspace_leave"
    HEARTBEAT = "heartbeat"
    SYNC_ACK = "sync_ack"
    PRESENCE_UPDATE = "presence_update"
    SYNC_OPERATION = "sync_operation"


class ServerEventType(StrEnum):
    """Events that the server may send over WebSocket connections."""

    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    FILE_RENAMED = "file_renamed"
    WORKSPACE_UPDATED = "workspace_updated"
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    SYNC_REQUIRED = "sync_required"
    PRESENCE_CHANGED = "presence_changed"

