"""Adapter around the current local workspace indexer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from devsync.scanner import ScanSummary, scan_workspace, workspace_status
from devsync.workspace import ensure_workspace, init_workspace


@dataclass(frozen=True)
class LocalWorkspaceIndexer:
    """Indexes a local DevSync workspace into SQLite and chunk storage."""

    root: Path

    def initialize(self, name: str | None = None) -> Path:
        """Initialize the workspace and return its metadata directory."""
        workspace = init_workspace(self.root, name)
        return workspace.meta_dir

    def scan(self) -> ScanSummary:
        """Scan the workspace and return a summary."""
        workspace = ensure_workspace(self.root)
        return scan_workspace(workspace)

    def status(self) -> dict[str, int | str | None]:
        """Return workspace status from the local metadata database."""
        workspace = ensure_workspace(self.root)
        return workspace_status(workspace)

