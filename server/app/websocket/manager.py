"""In-process WebSocket connection manager."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from starlette.websockets import WebSocket

from server.app.sync.models import SyncEvent
from server.app.websocket.events import sync_event_to_message
from server.app.websocket.schemas import DeviceConnectedEvent, DeviceDisconnectedEvent


@dataclass
class WebSocketConnection:
    """Tracked WebSocket connection metadata."""

    id: UUID
    websocket: WebSocket
    user_id: UUID
    device_id: UUID | None = None
    device_name: str | None = None
    joined_workspaces: set[UUID] = field(default_factory=set)
    workspace_devices: dict[UUID, UUID] = field(default_factory=dict)
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebSocketManager:
    """Tracks active connections and workspace rooms."""

    def __init__(self) -> None:
        """Create manager."""
        self._connections: dict[UUID, WebSocketConnection] = {}
        self._rooms: dict[UUID, set[UUID]] = {}

    @property
    def connection_count(self) -> int:
        """Return active connection count."""
        return len(self._connections)

    def room_size(self, workspace_id: UUID) -> int:
        """Return room subscription count."""
        return len(self._rooms.get(workspace_id, set()))

    async def connect(self, websocket: WebSocket, user_id: UUID) -> WebSocketConnection:
        """Accept and track a connection."""
        await websocket.accept()
        connection = WebSocketConnection(id=uuid.uuid4(), websocket=websocket, user_id=user_id)
        self._connections[connection.id] = connection
        return connection

    async def join_workspace(self, connection: WebSocketConnection, workspace_id: UUID, device_id: UUID, device_name: str) -> None:
        """Subscribe a connection to a workspace."""
        connection.device_id = device_id
        connection.device_name = device_name
        connection.joined_workspaces.add(workspace_id)
        connection.workspace_devices[workspace_id] = device_id
        self._rooms.setdefault(workspace_id, set()).add(connection.id)
        await self.broadcast_presence_connected(workspace_id, device_id, device_name, exclude_connection_id=connection.id)

    async def leave_workspace(self, connection: WebSocketConnection, workspace_id: UUID) -> None:
        """Unsubscribe a connection from a workspace."""
        device_id = connection.workspace_devices.get(workspace_id)
        connection.joined_workspaces.discard(workspace_id)
        connection.workspace_devices.pop(workspace_id, None)
        room = self._rooms.get(workspace_id)
        if room is not None:
            room.discard(connection.id)
            if not room:
                self._rooms.pop(workspace_id, None)
        if device_id is not None:
            await self.broadcast_presence_disconnected(workspace_id, device_id, exclude_connection_id=connection.id)

    async def disconnect(self, connection: WebSocketConnection) -> None:
        """Remove connection and notify rooms."""
        for workspace_id in list(connection.joined_workspaces):
            await self.leave_workspace(connection, workspace_id)
        self._connections.pop(connection.id, None)

    async def touch_heartbeat(self, connection: WebSocketConnection) -> None:
        """Update connection heartbeat timestamp."""
        connection.last_heartbeat = datetime.now(timezone.utc)

    async def send(self, connection: WebSocketConnection, message: dict[str, object]) -> None:
        """Send JSON to a connection."""
        await connection.websocket.send_json(message)

    async def send_error(self, connection: WebSocketConnection, code: str, message: str) -> None:
        """Send a standardized error message."""
        await self.send(connection, {"type": "error", "code": code, "message": message})

    async def broadcast_sync_event(self, event: SyncEvent, sender_device_id: UUID | None = None) -> None:
        """Broadcast a sync event to subscribers except the sender device."""
        message = sync_event_to_message(event)
        for connection in self._connections_for_workspace(event.workspace_id):
            if sender_device_id is not None and connection.workspace_devices.get(event.workspace_id) == sender_device_id:
                continue
            await self.send(connection, message)

    async def broadcast_presence_connected(
        self,
        workspace_id: UUID,
        device_id: UUID,
        device_name: str,
        exclude_connection_id: UUID | None = None,
    ) -> None:
        """Broadcast device connected presence."""
        message = DeviceConnectedEvent(
            workspace_id=workspace_id,
            device_id=device_id,
            device_name=device_name,
        ).model_dump(mode="json")
        await self._broadcast(workspace_id, message, exclude_connection_id)

    async def broadcast_presence_disconnected(
        self,
        workspace_id: UUID,
        device_id: UUID,
        exclude_connection_id: UUID | None = None,
    ) -> None:
        """Broadcast device disconnected presence."""
        message = DeviceDisconnectedEvent(workspace_id=workspace_id, device_id=device_id).model_dump(mode="json")
        await self._broadcast(workspace_id, message, exclude_connection_id)

    async def _broadcast(self, workspace_id: UUID, message: dict[str, object], exclude_connection_id: UUID | None = None) -> None:
        """Broadcast a message to a workspace room."""
        for connection in self._connections_for_workspace(workspace_id):
            if connection.id == exclude_connection_id:
                continue
            await self.send(connection, message)

    def _connections_for_workspace(self, workspace_id: UUID) -> list[WebSocketConnection]:
        """Return active room connections."""
        return [
            self._connections[connection_id]
            for connection_id in self._rooms.get(workspace_id, set())
            if connection_id in self._connections
        ]


websocket_manager = WebSocketManager()

