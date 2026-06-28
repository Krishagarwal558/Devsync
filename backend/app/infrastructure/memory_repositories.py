"""In-memory backend repositories for development and tests."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from backend.app.application.repositories import (
    DeviceRepository,
    SyncOperationRepository,
    UserRepository,
    WorkspaceRepository,
)
from backend.app.domain.identity import Device, User
from backend.app.domain.sync import SyncOperation
from backend.app.domain.workspaces import Workspace, WorkspaceMember


class InMemoryUserRepository(UserRepository):
    """Stores users in process memory."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._users: dict[UUID, User] = {}
        self._email_index: dict[str, UUID] = {}

    def add(self, user: User) -> None:
        """Persist a user."""
        self._users[user.id] = user
        self._email_index[user.email] = user.id

    def get_by_email(self, email: str) -> User | None:
        """Return a user by normalized email."""
        user_id = self._email_index.get(email.lower().strip())
        return self._users.get(user_id) if user_id else None

    def get(self, user_id: UUID) -> User | None:
        """Return a user by id."""
        return self._users.get(user_id)


class InMemoryDeviceRepository(DeviceRepository):
    """Stores devices in process memory."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._devices: dict[UUID, Device] = {}

    def add(self, device: Device) -> None:
        """Persist a device."""
        self._devices[device.id] = device

    def get(self, device_id: UUID) -> Device | None:
        """Return a device by id."""
        return self._devices.get(device_id)

    def save(self, device: Device) -> None:
        """Update an existing device."""
        self._devices[device.id] = device


class InMemoryWorkspaceRepository(WorkspaceRepository):
    """Stores workspaces and memberships in process memory."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._workspaces: dict[UUID, Workspace] = {}
        self._members: dict[UUID, list[WorkspaceMember]] = defaultdict(list)

    def add(self, workspace: Workspace) -> None:
        """Persist a workspace."""
        self._workspaces[workspace.id] = workspace

    def get(self, workspace_id: UUID) -> Workspace | None:
        """Return a workspace by id."""
        return self._workspaces.get(workspace_id)

    def save(self, workspace: Workspace) -> None:
        """Update an existing workspace."""
        self._workspaces[workspace.id] = workspace

    def add_member(self, member: WorkspaceMember) -> None:
        """Persist a workspace member."""
        existing = self._members[member.workspace_id]
        self._members[member.workspace_id] = [
            item for item in existing if item.user_id != member.user_id
        ]
        self._members[member.workspace_id].append(member)

    def list_for_user(self, user_id: UUID) -> list[Workspace]:
        """Return workspaces visible to a user."""
        workspace_ids = [
            workspace_id
            for workspace_id, members in self._members.items()
            if any(member.user_id == user_id for member in members)
        ]
        return [self._workspaces[item] for item in workspace_ids if item in self._workspaces]


class InMemorySyncOperationRepository(SyncOperationRepository):
    """Stores sequenced sync operations in process memory."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._operations: dict[UUID, list[SyncOperation]] = defaultdict(list)

    def append(self, operation: SyncOperation) -> SyncOperation:
        """Persist and sequence a sync operation."""
        sequence = len(self._operations[operation.workspace_id]) + 1
        sequenced = operation.assign_sequence(sequence)
        self._operations[operation.workspace_id].append(sequenced)
        return sequenced

    def list_after(self, workspace_id: UUID, sequence: int) -> list[SyncOperation]:
        """Return operations after a sequence."""
        return [
            operation
            for operation in self._operations.get(workspace_id, [])
            if operation.sequence is not None and operation.sequence > sequence
        ]

