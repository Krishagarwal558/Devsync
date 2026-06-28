"""Adapter around local folder-to-folder synchronization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from devsync.syncer import SyncSummary, sync_workspace
from devsync.workspace import find_workspace


@dataclass(frozen=True)
class LocalFolderSyncService:
    """Synchronizes one local workspace folder into another folder."""

    source: Path

    def sync_to(self, target: Path, delete: bool = False, force: bool = False, dry_run: bool = False) -> SyncSummary:
        """Sync the source workspace into a target folder."""
        return sync_workspace(find_workspace(self.source), target, delete=delete, force=force, dry_run=dry_run)

