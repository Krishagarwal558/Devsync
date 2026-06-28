from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from server.app.sync.models import SyncEvent
from server.app.websocket.manager import WebSocketManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, object]) -> None:
        self.messages.append(message)


@pytest.mark.anyio
async def test_manager_tracks_rooms_broadcasts_and_cleans_up() -> None:
    manager = WebSocketManager()
    workspace_id = uuid.uuid4()
    sender_device_id = uuid.uuid4()
    receiver_device_id = uuid.uuid4()
    sender_socket = FakeWebSocket()
    receiver_socket = FakeWebSocket()

    sender = await manager.connect(sender_socket, uuid.uuid4())  # type: ignore[arg-type]
    receiver = await manager.connect(receiver_socket, uuid.uuid4())  # type: ignore[arg-type]
    await manager.join_workspace(sender, workspace_id, sender_device_id, "Sender")
    await manager.join_workspace(receiver, workspace_id, receiver_device_id, "Receiver")
    event = SyncEvent(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        sender_device_id=sender_device_id,
        sequence=7,
        event_type="file_modified",
        path="src/app.py",
        payload={"metadata": {"version_id": "v1"}},
        checksum="abc",
        bandwidth_bytes=128,
        status="accepted",
        created_at=datetime.now(timezone.utc),
    )

    await manager.broadcast_sync_event(event, sender_device_id=sender_device_id)

    assert manager.room_size(workspace_id) == 2
    assert not any(message.get("type") == "sync_event" for message in sender_socket.messages)
    assert any(message.get("type") == "sync_event" and message.get("sequence") == 7 for message in receiver_socket.messages)

    await manager.disconnect(receiver)

    assert manager.connection_count == 1
    assert manager.room_size(workspace_id) == 1

