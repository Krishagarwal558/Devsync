"""Adapter around local snapshot storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from devsync.snapshots import SnapshotRecord, create_snapshot, list_snapshots, restore_snapshot
from devsync.workspace import ensure_workspace


@dataclass(frozen=True)
class LocalSnapshotService:
    """Creates, lists, and restores local workspace snapshots."""

    root: Path

    def create(self, name: str) -> SnapshotRecord:
        """Create a named snapshot."""
        return create_snapshot(ensure_workspace(self.root), name)

    def list(self) -> list[SnapshotRecord]:
        """List snapshots newest first."""
        return list_snapshots(ensure_workspace(self.root))

    def restore(self, snapshot_id: str, delete_extra: bool = False) -> int:
        """Restore a snapshot and return the number of files restored."""
        return restore_snapshot(ensure_workspace(self.root), snapshot_id, delete_extra)

