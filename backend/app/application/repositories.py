"""Repository interfaces for backend application services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.app.domain.identity import Device, User
from backend.app.domain.sync import SyncOperation
from backend.app.domain.workspaces import Workspace, WorkspaceMember


class UserRepository(ABC):
    """Persistence port for users."""

    @abstractmethod
    def add(self, user: User) -> None:
        """Persist a user."""

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Return a user by normalized email."""

    @abstractmethod
    def get(self, user_id: UUID) -> User | None:
        """Return a user by id."""


class DeviceRepository(ABC):
    """Persistence port for devices."""

    @abstractmethod
    def add(self, device: Device) -> None:
        """Persist a device."""

    @abstractmethod
    def get(self, device_id: UUID) -> Device | None:
        """Return a device by id."""

    @abstractmethod
    def save(self, device: Device) -> None:
        """Update an existing device."""


class WorkspaceRepository(ABC):
    """Persistence port for workspaces and memberships."""

    @abstractmethod
    def add(self, workspace: Workspace) -> None:
        """Persist a workspace."""

    @abstractmethod
    def get(self, workspace_id: UUID) -> Workspace | None:
        """Return a workspace by id."""

    @abstractmethod
    def save(self, workspace: Workspace) -> None:
        """Update an existing workspace."""

    @abstractmethod
    def add_member(self, member: WorkspaceMember) -> None:
        """Persist a workspace member."""

    @abstractmethod
    def list_for_user(self, user_id: UUID) -> list[Workspace]:
        """Return workspaces visible to a user."""


class SyncOperationRepository(ABC):
    """Persistence port for sync operation sequencing."""

    @abstractmethod
    def append(self, operation: SyncOperation) -> SyncOperation:
        """Persist and sequence a sync operation."""

    @abstractmethod
    def list_after(self, workspace_id: UUID, sequence: int) -> list[SyncOperation]:
        """Return operations after a sequence."""

