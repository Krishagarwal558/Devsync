"""Synchronization use cases."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.app.application.repositories import SyncOperationRepository, WorkspaceRepository
from backend.app.domain.sync import SyncOperation, SyncOperationType
from shared.devsync_shared.errors import NotFoundError


@dataclass(frozen=True)
class SubmitSyncOperationCommand:
    """Input data for submitting a sync operation."""

    workspace_id: UUID
    device_id: UUID
    operation_type: SyncOperationType
    path: str
    payload: dict[str, object]


class SubmitSyncOperationUseCase:
    """Validates and sequences sync operations."""

    def __init__(self, workspaces: WorkspaceRepository, operations: SyncOperationRepository) -> None:
        """Create the use case."""
        self._workspaces = workspaces
        self._operations = operations

    def execute(self, command: SubmitSyncOperationCommand) -> SyncOperation:
        """Create a sequenced sync operation."""
        if self._workspaces.get(command.workspace_id) is None:
            raise NotFoundError("Workspace not found")
        operation = SyncOperation.create(
            workspace_id=command.workspace_id,
            device_id=command.device_id,
            operation_type=command.operation_type,
            path=command.path,
            payload=command.payload,
        )
        return self._operations.append(operation)

