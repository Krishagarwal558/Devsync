"""Storage provider abstraction and local filesystem implementation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID

from server.app.utils.errors import ResourceConflict, ResourceNotFound


@dataclass(frozen=True)
class StoredObjectMetadata:
    """Metadata produced while writing a stored object."""

    size_bytes: int
    checksum: str


class StorageProvider(Protocol):
    """Storage provider interface for file version blobs."""

    def save_file(self, workspace_id: UUID, storage_key: str, stream: BinaryIO, max_bytes: int) -> StoredObjectMetadata:
        """Save a stream and return content metadata."""

    def read_file(self, workspace_id: UUID, storage_key: str) -> BinaryIO:
        """Open a stored file for reading."""

    def delete_file(self, workspace_id: UUID, storage_key: str) -> None:
        """Delete a stored file if it exists."""

    def exists(self, workspace_id: UUID, storage_key: str) -> bool:
        """Return whether an object exists."""

    def checksum(self, workspace_id: UUID, storage_key: str) -> str:
        """Return sha256 checksum for a stored object."""


class LocalStorageProvider:
    """Local filesystem storage provider for the MVP."""

    def __init__(self, root: str | Path) -> None:
        """Create local provider rooted at `root`."""
        self._root = Path(root).resolve()

    def save_file(self, workspace_id: UUID, storage_key: str, stream: BinaryIO, max_bytes: int) -> StoredObjectMetadata:
        """Save a stream under the workspace root."""
        destination = self._resolve(workspace_id, storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with destination.open("wb") as output:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise ResourceConflict("Upload exceeds configured size limit")
                digest.update(chunk)
                output.write(chunk)
        return StoredObjectMetadata(size_bytes=size, checksum=digest.hexdigest())

    def read_file(self, workspace_id: UUID, storage_key: str) -> BinaryIO:
        """Open a stored object for reading."""
        path = self._resolve(workspace_id, storage_key)
        if not path.exists():
            raise ResourceNotFound("Stored file blob not found")
        return path.open("rb")

    def delete_file(self, workspace_id: UUID, storage_key: str) -> None:
        """Delete a stored object if it exists."""
        self._resolve(workspace_id, storage_key).unlink(missing_ok=True)

    def exists(self, workspace_id: UUID, storage_key: str) -> bool:
        """Return whether an object exists."""
        return self._resolve(workspace_id, storage_key).exists()

    def checksum(self, workspace_id: UUID, storage_key: str) -> str:
        """Return sha256 checksum for a stored object."""
        path = self._resolve(workspace_id, storage_key)
        if not path.exists():
            raise ResourceNotFound("Stored file blob not found")
        digest = hashlib.sha256()
        with path.open("rb") as input_file:
            while True:
                chunk = input_file.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _resolve(self, workspace_id: UUID, storage_key: str) -> Path:
        """Resolve storage key while preventing path traversal."""
        workspace_root = (self._root / "workspaces" / str(workspace_id)).resolve()
        resolved = (workspace_root / storage_key).resolve()
        if workspace_root not in resolved.parents and resolved != workspace_root:
            raise ResourceConflict("Invalid storage key")
        return resolved
