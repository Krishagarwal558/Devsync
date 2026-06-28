"""Desktop sync orchestration service."""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from uuid import UUID

from desktop.app.core.file_client import FileClient
from desktop.app.core.ignore_rules import IgnoreRules
from desktop.app.core.local_state import LocalStateStore
from desktop.app.core.path_utils import local_path_for_remote, remote_path_for_local, sha256_file
from desktop.app.core.websocket_client import RealtimeWebSocketClient


class DesktopSyncService:
    """Coordinates local watcher, uploads, realtime downloads, and loop prevention."""

    def __init__(
        self,
        state: LocalStateStore,
        file_client: FileClient,
        server_url: str,
        access_token: str,
        ignore_rules: IgnoreRules | None = None,
        remote_apply_seconds: float = 3.0,
    ) -> None:
        self._state = state
        self._file_client = file_client
        self._server_url = server_url
        self._access_token = access_token
        self._ignore_rules = ignore_rules or IgnoreRules()
        self._remote_apply_seconds = remote_apply_seconds
        self._remote_applying: dict[str, float] = {}
        self._ws_client: RealtimeWebSocketClient | None = None

    async def upload_changed_file(self, local_path: Path) -> dict[str, object] | None:
        """Upload a changed local file if checksum differs from local state."""
        workspace_id, device_id, root = self._required_binding()
        if self._ignore_rules.is_ignored_local_path(root, local_path):
            return None
        remote_path = remote_path_for_local(root, local_path)
        if self.is_remote_applying(remote_path):
            return None
        checksum = sha256_file(local_path)
        if self._state.get_known_checksum(workspace_id, remote_path) == checksum:
            return None
        try:
            response = await self._file_client.upload_file(str(workspace_id), str(device_id), local_path, remote_path, checksum)
        except Exception:
            self._state.enqueue("upload", workspace_id, remote_path, {"local_path": str(local_path), "checksum": checksum})
            self._state.add_activity(f"Queued upload retry for {remote_path}.")
            raise
        self._state.save_known_file(
            workspace_id,
            remote_path,
            checksum,
            file_id=str(response["file_id"]),
            version_id=str(response["version_id"]),
        )
        self._state.add_activity(f"Uploaded {remote_path}.")
        return response

    async def handle_local_deleted_file(self, local_path: Path) -> None:
        """Soft delete cloud file when a known local file is deleted."""
        workspace_id, _, root = self._required_binding()
        remote_path = remote_path_for_local(root, local_path)
        known = self._state.get_known_file(workspace_id, remote_path)
        if not known or not known.get("file_id"):
            return
        try:
            await self._file_client.delete_file(str(workspace_id), str(known["file_id"]))
        except Exception:
            self._state.enqueue("upload", workspace_id, remote_path, {"delete_file_id": known["file_id"]})
            self._state.add_activity(f"Queued delete retry for {remote_path}.")
            raise
        self._state.delete_known_file(workspace_id, remote_path)
        self._state.add_activity(f"Deleted {remote_path}.")

    async def handle_sync_event(self, message: dict[str, object]) -> None:
        """Handle a realtime sync_event from another device."""
        if message.get("type") != "sync_event":
            return
        workspace_id, _, root = self._required_binding()
        remote_path = str(message["path"])
        metadata = dict(dict(message.get("payload") or {}).get("metadata") or {})
        file_id = metadata.get("file_id")
        if not file_id:
            return
        destination = local_path_for_remote(root, remote_path)
        try:
            content = await self._file_client.download_file(str(workspace_id), str(file_id))
        except Exception:
            self._state.enqueue("download", workspace_id, remote_path, dict(message))
            self._state.add_activity(f"Queued download retry for {remote_path}.")
            raise
        checksum = str(message.get("checksum") or "")
        self.apply_remote_file(destination, remote_path, content, checksum)
        sequence = int(message.get("sequence") or 0)
        self._state.save_setting("last_sequence", str(sequence))
        self._state.add_activity(f"Downloaded {remote_path}.")

    def apply_remote_file(self, destination: Path, remote_path: str, content: bytes, checksum: str) -> None:
        """Write remote content safely with conflict handling."""
        workspace_id, _, _ = self._required_binding()
        current_known = self._state.get_known_checksum(workspace_id, remote_path)
        if destination.exists() and current_known and sha256_file(destination) != current_known:
            self._write_conflict_files(destination, content)
            self._state.add_activity(f"Conflict detected for {remote_path}.")
            return
        self.mark_remote_applying(remote_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup = destination.with_name(f"{destination.name}.bak")
        if destination.exists():
            shutil.copy2(destination, backup)
        temp = destination.with_name(f".{destination.name}.devsync-tmp")
        temp.write_bytes(content)
        temp.replace(destination)
        self._state.save_known_file(workspace_id, remote_path, checksum)

    def mark_remote_applying(self, remote_path: str) -> None:
        """Mark a path as being written from remote to prevent re-upload loops."""
        self._remote_applying[remote_path] = time.monotonic() + self._remote_apply_seconds

    def is_remote_applying(self, remote_path: str) -> bool:
        """Return whether path should be ignored by watcher due to remote write."""
        expires_at = self._remote_applying.get(remote_path)
        if expires_at is None:
            return False
        if expires_at <= time.monotonic():
            self._remote_applying.pop(remote_path, None)
            return False
        return True

    async def start_realtime(self) -> None:
        """Start realtime WebSocket connection."""
        workspace_id = self._state.get_setting("workspace_id")
        device_id = self._state.get_setting("device_id")
        last_sequence = int(self._state.get_setting("last_sequence") or "0")
        if not workspace_id or not device_id:
            raise RuntimeError("Workspace and device must be configured before realtime sync")
        self._ws_client = RealtimeWebSocketClient(
            self._server_url,
            self._access_token,
            workspace_id,
            device_id,
            last_sequence,
            self.handle_sync_event,
        )
        await self._ws_client.run_forever()

    async def stop_realtime(self) -> None:
        """Stop realtime WebSocket connection."""
        if self._ws_client is not None:
            await self._ws_client.stop()

    async def retry_pending(self) -> tuple[int, int]:
        """Retry pending upload and download queue items."""
        workspace_id, device_id, _ = self._required_binding()
        completed_upload_ids: list[int] = []
        completed_download_ids: list[int] = []
        for item in self._state.list_queue("upload"):
            payload = dict(item["payload"])
            remote_path = str(item["path"])
            if payload.get("delete_file_id"):
                await self._file_client.delete_file(str(workspace_id), str(payload["delete_file_id"]))
            else:
                local_path = Path(str(payload["local_path"]))
                checksum = str(payload["checksum"])
                response = await self._file_client.upload_file(str(workspace_id), str(device_id), local_path, remote_path, checksum)
                self._state.save_known_file(
                    workspace_id,
                    remote_path,
                    checksum,
                    file_id=str(response["file_id"]),
                    version_id=str(response["version_id"]),
                )
            completed_upload_ids.append(int(item["id"]))
        for item in self._state.list_queue("download"):
            await self.handle_sync_event(dict(item["payload"]))
            completed_download_ids.append(int(item["id"]))
        self._state.remove_queue_items(completed_upload_ids + completed_download_ids)
        if completed_upload_ids or completed_download_ids:
            self._state.add_activity(f"Retried {len(completed_upload_ids)} uploads and {len(completed_download_ids)} downloads.")
        return len(completed_upload_ids), len(completed_download_ids)

    def start_realtime_background(self) -> asyncio.Task[None]:
        """Start realtime connection on current event loop."""
        return asyncio.create_task(self.start_realtime())

    def _required_binding(self) -> tuple[object, object, Path]:
        workspace_id = self._state.get_setting("workspace_id")
        device_id = self._state.get_setting("device_id")
        local_folder = self._state.get_setting("local_folder_path")
        if not workspace_id or not device_id or not local_folder:
            raise RuntimeError("Workspace, device, and local folder must be configured")
        return UUID(workspace_id), UUID(device_id), Path(local_folder)

    def _write_conflict_files(self, destination: Path, remote_content: bytes) -> None:
        local_conflict = destination.with_name(f"{destination.name}.LOCAL-CONFLICT")
        remote_conflict = destination.with_name(f"{destination.name}.REMOTE-CONFLICT")
        if destination.exists():
            shutil.copy2(destination, local_conflict)
        remote_conflict.write_bytes(remote_content)
