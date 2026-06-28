"""Realtime event formatting and dispatch."""

from __future__ import annotations

from uuid import UUID

from server.app.sync.models import SyncEvent
from server.app.websocket.schemas import SyncEventMessage


def sync_event_to_message(event: SyncEvent) -> dict[str, object]:
    """Convert a sync event model into a WebSocket message."""
    payload = dict(event.payload or {})
    return SyncEventMessage(
        workspace_id=event.workspace_id,
        sequence=event.sequence,
        event_type=event.event_type,
        path=event.path,
        payload=payload,
        checksum=event.checksum,
        size_bytes=event.bandwidth_bytes,
        created_at=event.created_at,
    ).model_dump(mode="json")


class RealtimeEventDispatcher:
    """Dispatch sync events to active realtime subscribers."""

    def __init__(self) -> None:
        """Create dispatcher."""
        self._manager: object | None = None

    def bind_manager(self, manager: object) -> None:
        """Bind the active WebSocket manager."""
        self._manager = manager

    async def publish_sync_event(self, event: SyncEvent, sender_device_id: UUID | None = None) -> None:
        """Publish a sync event to joined workspace devices."""
        if self._manager is None:
            return
        await self._manager.broadcast_sync_event(event, sender_device_id=sender_device_id)  # type: ignore[attr-defined]


realtime_dispatcher = RealtimeEventDispatcher()

