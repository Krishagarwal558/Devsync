"""Dashboard view model for the desktop application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.devsync_core.files.local_indexer import LocalWorkspaceIndexer
from devsync.syncer import SyncSummary, sync_workspace
from devsync.workspace import find_workspace


@dataclass
class DashboardState:
    """State shown by the dashboard."""

    workspace_path: Path | None
    active_files: int
    chunks: int
    snapshots: int
    tracked_bytes: int
    sync_status: str
    target_path: Path | None = None


class DashboardViewModel:
    """Coordinates dashboard state without depending on PySide6 widgets."""

    def __init__(self) -> None:
        """Create an empty dashboard view model."""
        self._state = DashboardState(
            workspace_path=None,
            active_files=0,
            chunks=0,
            snapshots=0,
            tracked_bytes=0,
            sync_status="idle",
        )

    @property
    def state(self) -> DashboardState:
        """Return the latest dashboard state."""
        return self._state

    def open_workspace(self, path: Path) -> DashboardState:
        """Load workspace status into dashboard state."""
        indexer = LocalWorkspaceIndexer(path)
        status = indexer.status()
        self._state = DashboardState(
            workspace_path=path,
            active_files=int(status["active_files"] or 0),
            chunks=int(status["chunks"] or 0),
            snapshots=int(status["snapshots"] or 0),
            tracked_bytes=int(status["tracked_bytes"] or 0),
            sync_status="ready",
            target_path=self._state.target_path,
        )
        return self._state

    def create_workspace(self, path: Path, name: str) -> DashboardState:
        """Initialize and scan a workspace."""
        indexer = LocalWorkspaceIndexer(path)
        indexer.initialize(name)
        indexer.scan()
        return self.open_workspace(path)

    def scan_workspace(self) -> DashboardState:
        """Scan the current workspace and refresh state."""
        if self._state.workspace_path is None:
            return self._state
        LocalWorkspaceIndexer(self._state.workspace_path).scan()
        return self.open_workspace(self._state.workspace_path)

    def set_target(self, path: Path) -> DashboardState:
        """Set the target folder used for local device simulation."""
        self._state.target_path = path
        return self._state

    def sync_now(self) -> SyncSummary | None:
        """Run a one-time sync from the current workspace to the selected target."""
        if self._state.workspace_path is None or self._state.target_path is None:
            return None
        source = find_workspace(self._state.workspace_path)
        return sync_workspace(source, self._state.target_path)
