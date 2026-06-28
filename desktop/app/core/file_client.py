"""File REST client."""

from __future__ import annotations

from pathlib import Path

from desktop.app.core.auth_client import AuthorizedClient


class FileClient:
    """Client for file upload/download APIs."""

    def __init__(self, authorized: AuthorizedClient) -> None:
        self._authorized = authorized

    async def upload_file(self, workspace_id: str, device_id: str, local_file: Path, remote_path: str, checksum: str) -> dict[str, object]:
        """Upload a file version."""
        async with self._authorized.client() as client:
            with local_file.open("rb") as input_file:
                response = await client.post(
                    f"/v1/workspaces/{workspace_id}/files/upload",
                    data={"path": remote_path, "sender_device_id": device_id, "checksum": checksum, "file_type": "file"},
                    files={"file": (local_file.name, input_file, "application/octet-stream")},
                )
        response.raise_for_status()
        return response.json()

    async def list_files(self, workspace_id: str, prefix: str | None = None) -> dict[str, object]:
        """List cloud files."""
        params = {"prefix": prefix} if prefix else None
        async with self._authorized.client() as client:
            response = await client.get(f"/v1/workspaces/{workspace_id}/files", params=params)
            response.raise_for_status()
            return response.json()

    async def download_file(self, workspace_id: str, file_id: str) -> bytes:
        """Download current file bytes."""
        async with self._authorized.client() as client:
            response = await client.get(f"/v1/workspaces/{workspace_id}/files/{file_id}/download")
            response.raise_for_status()
            return response.content

    async def delete_file(self, workspace_id: str, file_id: str) -> None:
        """Soft delete a cloud file."""
        async with self._authorized.client() as client:
            response = await client.delete(f"/v1/workspaces/{workspace_id}/files/{file_id}")
            response.raise_for_status()
