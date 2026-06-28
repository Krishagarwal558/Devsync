from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from server.app.auth.models import User
from server.app.devices.models import Device
from server.app.sync.models import SyncEvent
from server.app.utils.errors import PermissionDenied
from server.app.websocket.manager import WebSocketManager
from server.app.websocket.schemas import DeviceHeartbeatMessage, WorkspaceJoinMessage
from server.app.websocket.services import WebSocketGatewayService
from server.app.workspaces.models import Workspace, WorkspaceMember


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, message: dict[str, object]) -> None:
        self.messages.append(message)


class UnitOfWorkStub:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class WorkspaceRepositoryStub:
    def __init__(self, workspace: Workspace, membership: WorkspaceMember) -> None:
        self.workspace = workspace
        self.membership = membership

    async def get_visible_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Workspace, WorkspaceMember] | None:
        if self.workspace.id == workspace_id and self.membership.user_id == user_id:
            return self.workspace, self.membership
        return None


class DeviceRepositoryStub:
    def __init__(self, device: Device) -> None:
        self.device = device

    async def get_for_user(self, device_id: uuid.UUID, user_id: uuid.UUID, include_deleted: bool = False) -> Device | None:
        if self.device.id == device_id and self.device.user_id == user_id:
            return self.device
        return None

    async def heartbeat(self, device: Device) -> Device:
        device.last_seen_at = datetime.now(timezone.utc)
        return device


class SyncRepositoryStub:
    def __init__(self, events: list[SyncEvent]) -> None:
        self.events = events
        self.ack_sequence: int | None = None

    async def replay_events(self, workspace_id: uuid.UUID, after_sequence: int, limit: int) -> list[SyncEvent]:
        return [event for event in self.events if event.workspace_id == workspace_id and event.sequence > after_sequence][:limit]

    async def acknowledge_up_to_sequence(self, workspace_id: uuid.UUID, up_to_sequence: int) -> int:
        self.ack_sequence = up_to_sequence
        return len([event for event in self.events if event.workspace_id == workspace_id and event.sequence <= up_to_sequence])


def make_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="owner@example.com",
        display_name="Owner",
        password_hash="hash",
        status="active",
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


def make_workspace(user: User) -> tuple[Workspace, WorkspaceMember]:
    now = datetime.now(timezone.utc)
    workspace = Workspace(
        id=uuid.uuid4(),
        owner_id=user.id,
        name="Project",
        slug="project",
        status="active",
        settings={},
        archived_at=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        status="active",
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    return workspace, membership


def make_device(user: User, trust_status: str = "trusted") -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Krish Laptop",
        platform="windows",
        public_key="key",
        trust_status=trust_status,
        last_seen_at=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


def make_service(trust_status: str = "trusted"):
    user = make_user()
    workspace, membership = make_workspace(user)
    device = make_device(user, trust_status)
    replay_event = SyncEvent(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        sender_device_id=uuid.uuid4(),
        sequence=42,
        event_type="file_modified",
        path="src/app.py",
        payload={"metadata": {"file_id": "file"}},
        checksum="abc",
        bandwidth_bytes=10,
        status="accepted",
        created_at=datetime.now(timezone.utc),
    )
    manager = WebSocketManager()
    db = UnitOfWorkStub()
    sync_repo = SyncRepositoryStub([replay_event])
    service = WebSocketGatewayService(
        db,  # type: ignore[arg-type]
        token_service=None,  # type: ignore[arg-type]
        auth_repository=None,  # type: ignore[arg-type]
        workspace_repository=WorkspaceRepositoryStub(workspace, membership),  # type: ignore[arg-type]
        device_repository=DeviceRepositoryStub(device),  # type: ignore[arg-type]
        sync_repository=sync_repo,  # type: ignore[arg-type]
        manager=manager,
    )
    return service, manager, db, sync_repo, user, workspace, device


@pytest.mark.anyio
async def test_join_workspace_replays_events_and_sends_joined() -> None:
    service, manager, _, _, user, workspace, device = make_service()
    socket = FakeWebSocket()
    connection = await manager.connect(socket, user.id)  # type: ignore[arg-type]

    await service.join_workspace(
        connection,
        user,
        WorkspaceJoinMessage(
            type="workspace_join",
            workspace_id=workspace.id,
            device_id=device.id,
            last_sequence=41,
        ),
    )

    assert manager.room_size(workspace.id) == 1
    assert socket.messages[0]["type"] == "sync_event"
    assert socket.messages[0]["sequence"] == 42
    assert socket.messages[-1]["type"] == "workspace_joined"
    assert socket.messages[-1]["replayed_events"] == 1


@pytest.mark.anyio
async def test_join_workspace_requires_trusted_device() -> None:
    service, manager, _, _, user, workspace, device = make_service(trust_status="pending")
    socket = FakeWebSocket()
    connection = await manager.connect(socket, user.id)  # type: ignore[arg-type]

    with pytest.raises(PermissionDenied):
        await service.join_workspace(
            connection,
            user,
            WorkspaceJoinMessage(
                type="workspace_join",
                workspace_id=workspace.id,
                device_id=device.id,
                last_sequence=0,
            ),
        )


@pytest.mark.anyio
async def test_device_heartbeat_updates_connection_and_device() -> None:
    service, manager, db, _, user, workspace, device = make_service()
    socket = FakeWebSocket()
    connection = await manager.connect(socket, user.id)  # type: ignore[arg-type]
    await manager.join_workspace(connection, workspace.id, device.id, device.name)

    await service.device_heartbeat(
        connection,
        user,
        DeviceHeartbeatMessage(type="device_heartbeat", workspace_id=workspace.id, device_id=device.id),
    )

    assert db.committed
    assert device.last_seen_at is not None

