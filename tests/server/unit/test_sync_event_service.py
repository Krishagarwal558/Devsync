from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from server.app.auth.models import User
from server.app.devices.models import Device
from server.app.sync.models import SyncEvent
from server.app.sync.schemas import AcknowledgeSyncEventsRequest, CreateSyncEventRequest
from server.app.sync.services import SyncEventService
from server.app.utils.errors import PermissionDenied, ResourceConflict, ResourceNotFound
from server.app.workspaces.models import Workspace, WorkspaceMember


class UnitOfWorkStub:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class WorkspaceRepositoryStub:
    def __init__(self, workspace: Workspace, membership: WorkspaceMember) -> None:
        self.workspace = workspace
        self.membership = membership

    async def get_visible_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Workspace, WorkspaceMember] | None:
        if self.workspace.id != workspace_id or self.membership.user_id != user_id:
            return None
        if self.membership.status != "active" or self.membership.deleted_at is not None:
            return None
        if self.workspace.status == "deleted" or self.workspace.deleted_at is not None:
            return None
        return self.workspace, self.membership


class DeviceRepositoryStub:
    def __init__(self, device: Device) -> None:
        self.device = device

    async def get_for_user(self, device_id: uuid.UUID, user_id: uuid.UUID, include_deleted: bool = False) -> Device | None:
        if self.device.id != device_id or self.device.user_id != user_id:
            return None
        if self.device.deleted_at is not None and not include_deleted:
            return None
        return self.device


class SyncEventRepositoryStub:
    def __init__(self) -> None:
        self.events: list[SyncEvent] = []
        self.locked_workspaces: list[uuid.UUID] = []

    async def lock_workspace_for_sequence(self, workspace_id: uuid.UUID) -> None:
        self.locked_workspaces.append(workspace_id)

    async def next_sequence(self, workspace_id: uuid.UUID) -> int:
        workspace_events = [event for event in self.events if event.workspace_id == workspace_id]
        return max((event.sequence for event in workspace_events), default=0) + 1

    async def find_duplicate(
        self,
        workspace_id: uuid.UUID,
        sender_device_id: uuid.UUID,
        event_type: str,
        path: str,
        payload: dict[str, object],
        checksum: str | None,
    ) -> SyncEvent | None:
        for event in self.events:
            if (
                event.workspace_id == workspace_id
                and event.sender_device_id == sender_device_id
                and event.event_type == event_type
                and event.path == path
                and event.payload == payload
                and event.checksum == checksum
            ):
                return event
        return None

    async def create_event(
        self,
        workspace_id: uuid.UUID,
        sender_device_id: uuid.UUID,
        sequence: int,
        event_type: str,
        path: str,
        payload: dict[str, object],
        checksum: str | None,
        bandwidth_bytes: int,
    ) -> SyncEvent:
        event = SyncEvent(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            sender_device_id=sender_device_id,
            sequence=sequence,
            event_type=event_type,
            path=path,
            payload=payload,
            checksum=checksum,
            bandwidth_bytes=bandwidth_bytes,
            status="accepted",
            created_at=datetime.now(timezone.utc),
        )
        self.events.append(event)
        return event

    async def list_events(self, workspace_id: uuid.UUID, limit: int, offset: int, after_sequence: int | None = None) -> list[SyncEvent]:
        events = [event for event in self.events if event.workspace_id == workspace_id]
        if after_sequence is not None:
            events = [event for event in events if event.sequence > after_sequence]
        return sorted(events, key=lambda event: event.sequence)[offset : offset + limit]

    async def replay_events(self, workspace_id: uuid.UUID, after_sequence: int, limit: int) -> list[SyncEvent]:
        events = [event for event in self.events if event.workspace_id == workspace_id and event.sequence > after_sequence]
        return sorted(events, key=lambda event: event.sequence)[:limit]

    async def acknowledge_by_ids(self, workspace_id: uuid.UUID, event_ids: list[uuid.UUID]) -> int:
        count = 0
        for event in self.events:
            if event.workspace_id == workspace_id and event.id in event_ids:
                event.status = "acknowledged"
                count += 1
        return count

    async def acknowledge_up_to_sequence(self, workspace_id: uuid.UUID, up_to_sequence: int) -> int:
        count = 0
        for event in self.events:
            if event.workspace_id == workspace_id and event.sequence <= up_to_sequence:
                event.status = "acknowledged"
                count += 1
        return count


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


def make_workspace(user: User, status: str = "active") -> tuple[Workspace, WorkspaceMember]:
    now = datetime.now(timezone.utc)
    workspace = Workspace(
        id=uuid.uuid4(),
        owner_id=user.id,
        name="Project",
        slug="project",
        status=status,
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
        name="Laptop",
        platform="windows",
        public_key="key",
        trust_status=trust_status,
        last_seen_at=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


def make_service(
    user: User,
    workspace_status: str = "active",
    device_trust_status: str = "trusted",
) -> tuple[SyncEventService, Workspace, Device, SyncEventRepositoryStub, UnitOfWorkStub]:
    db = UnitOfWorkStub()
    workspace, membership = make_workspace(user, workspace_status)
    device = make_device(user, device_trust_status)
    sync_repo = SyncEventRepositoryStub()
    service = SyncEventService(
        db,  # type: ignore[arg-type]
        sync_repo,  # type: ignore[arg-type]
        WorkspaceRepositoryStub(workspace, membership),  # type: ignore[arg-type]
        DeviceRepositoryStub(device),  # type: ignore[arg-type]
    )
    return service, workspace, device, sync_repo, db


@pytest.mark.anyio
async def test_create_event_assigns_workspace_sequence_numbers() -> None:
    user = make_user()
    service, workspace, device, sync_repo, db = make_service(user)

    first = await service.create_event(
        user,
        workspace.id,
        CreateSyncEventRequest(
            sender_device_id=device.id,
            event_type="file_created",
            path="src/app.py",
            checksum="abc",
        ),
    )
    second = await service.create_event(
        user,
        workspace.id,
        CreateSyncEventRequest(
            sender_device_id=device.id,
            event_type="file_modified",
            path="src/app.py",
            checksum="def",
        ),
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert sync_repo.locked_workspaces == [workspace.id, workspace.id]
    assert db.committed


@pytest.mark.anyio
async def test_duplicate_event_is_rejected() -> None:
    user = make_user()
    service, workspace, device, _, _ = make_service(user)
    request = CreateSyncEventRequest(
        sender_device_id=device.id,
        event_type="file_modified",
        path="src/app.py",
        checksum="abc",
    )

    await service.create_event(user, workspace.id, request)

    with pytest.raises(ResourceConflict):
        await service.create_event(user, workspace.id, request)


@pytest.mark.anyio
async def test_replay_returns_events_after_sequence() -> None:
    user = make_user()
    service, workspace, device, _, _ = make_service(user)
    for checksum in ["a", "b", "c"]:
        await service.create_event(
            user,
            workspace.id,
            CreateSyncEventRequest(
                sender_device_id=device.id,
                event_type="file_modified",
                path=f"file-{checksum}.txt",
                checksum=checksum,
            ),
        )

    replay = await service.replay_events(user, workspace.id, after_sequence=1, limit=10)

    assert [event.sequence for event in replay] == [2, 3]


@pytest.mark.anyio
async def test_history_pagination_orders_by_sequence() -> None:
    user = make_user()
    service, workspace, device, _, _ = make_service(user)
    for index in range(4):
        await service.create_event(
            user,
            workspace.id,
            CreateSyncEventRequest(
                sender_device_id=device.id,
                event_type="file_created",
                path=f"file-{index}.txt",
                checksum=str(index),
            ),
        )

    page = await service.list_events(user, workspace.id, limit=2, offset=1)

    assert [event.sequence for event in page] == [2, 3]


@pytest.mark.anyio
async def test_acknowledge_marks_events_processed() -> None:
    user = make_user()
    service, workspace, device, sync_repo, _ = make_service(user)
    event = await service.create_event(
        user,
        workspace.id,
        CreateSyncEventRequest(
            sender_device_id=device.id,
            event_type="file_created",
            path="file.txt",
            checksum="abc",
        ),
    )

    count = await service.acknowledge_events(
        user,
        workspace.id,
        AcknowledgeSyncEventsRequest(device_id=device.id, event_ids=[event.id]),
    )

    assert count == 1
    assert sync_repo.events[0].status == "acknowledged"


@pytest.mark.anyio
async def test_permissions_require_workspace_membership_and_trusted_device() -> None:
    user = make_user()
    other_user = make_user()
    service, workspace, device, _, _ = make_service(user, device_trust_status="pending")

    with pytest.raises(PermissionDenied):
        await service.create_event(
            user,
            workspace.id,
            CreateSyncEventRequest(
                sender_device_id=device.id,
                event_type="file_created",
                path="file.txt",
            ),
        )

    with pytest.raises(ResourceNotFound):
        await service.list_events(other_user, workspace.id, limit=10, offset=0)


@pytest.mark.anyio
async def test_archived_workspace_rejects_new_events() -> None:
    user = make_user()
    service, workspace, device, _, _ = make_service(user, workspace_status="archived")

    with pytest.raises(ResourceConflict):
        await service.create_event(
            user,
            workspace.id,
            CreateSyncEventRequest(
                sender_device_id=device.id,
                event_type="file_created",
                path="file.txt",
            ),
        )

