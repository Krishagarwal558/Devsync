"""Workspace setup service."""

from __future__ import annotations

from pathlib import Path

from desktop.app.core.local_state import LocalStateStore


class DesktopWorkspaceService:
    """Stores workspace-to-folder binding."""

    def __init__(self, state: LocalStateStore) -> None:
        self._state = state

    def bind_workspace(self, workspace_id: str, workspace_name: str, local_folder: Path) -> None:
        """Bind selected workspace to a local folder."""
        local_folder.mkdir(parents=True, exist_ok=True)
        self._state.save_setting("workspace_id", workspace_id)
        self._state.save_setting("workspace_name", workspace_name)
        self._state.save_setting("local_folder_path", str(local_folder))
        self._state.save_setting("last_sequence", self._state.get_setting("last_sequence") or "0")

