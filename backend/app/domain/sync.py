"""Synchronization domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from .identity import now_utc


class SyncOperationType(StrEnum):
    """Supported workspace file operations."""

    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    FILE_RENAMED = "file_renamed"
    SNAPSHOT_RESTORED = "snapshot_restored"


@dataclass(frozen=True)
class SyncOperation:
    """A durable synchronization operation for one workspace."""

    id: UUID
    workspace_id: UUID
    device_id: UUID
    operation_type: SyncOperationType
    path: str
    payload: dict[str, object]
    sequence: int | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        workspace_id: UUID,
        device_id: UUID,
        operation_type: SyncOperationType,
        path: str,
        payload: dict[str, object],
    ) -> "SyncOperation":
        """Create an unsequenced sync operation."""
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            device_id=device_id,
            operation_type=operation_type,
            path=path,
            payload=payload,
            sequence=None,
            created_at=now_utc(),
        )

    def assign_sequence(self, sequence: int) -> "SyncOperation":
        """Return a copy of the operation with a server sequence assigned."""
        return SyncOperation(
            id=self.id,
            workspace_id=self.workspace_id,
            device_id=self.device_id,
            operation_type=self.operation_type,
            path=self.path,
            payload=self.payload,
            sequence=sequence,
            created_at=self.created_at,
        )

