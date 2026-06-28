"""Storage provider abstraction and local filesystem implementation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
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


class R2StorageProvider:
    """Cloudflare R2 storage provider using the S3-compatible API."""

    def __init__(
        self,
        endpoint_url: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        """Create an R2 provider."""
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("boto3 is required when DEVSYNC_STORAGE_PROVIDER=r2") from exc

        self._bucket_name = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def save_file(self, workspace_id: UUID, storage_key: str, stream: BinaryIO, max_bytes: int) -> StoredObjectMetadata:
        """Upload a stream to R2 and return content metadata."""
        digest = hashlib.sha256()
        buffer = BytesIO()
        size = 0
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise ResourceConflict("Upload exceeds configured size limit")
            digest.update(chunk)
            buffer.write(chunk)
        buffer.seek(0)
        self._client.upload_fileobj(buffer, self._bucket_name, self._object_key(workspace_id, storage_key))
        return StoredObjectMetadata(size_bytes=size, checksum=digest.hexdigest())

    def read_file(self, workspace_id: UUID, storage_key: str) -> BinaryIO:
        """Download an R2 object into a readable stream."""
        try:
            response = self._client.get_object(Bucket=self._bucket_name, Key=self._object_key(workspace_id, storage_key))
        except Exception as exc:  # boto client raises generated ClientError subclasses.
            if self._is_missing_object(exc):
                raise ResourceNotFound("Stored file blob not found") from exc
            raise
        return response["Body"]

    def delete_file(self, workspace_id: UUID, storage_key: str) -> None:
        """Delete an R2 object if it exists."""
        self._client.delete_object(Bucket=self._bucket_name, Key=self._object_key(workspace_id, storage_key))

    def exists(self, workspace_id: UUID, storage_key: str) -> bool:
        """Return whether an R2 object exists."""
        try:
            self._client.head_object(Bucket=self._bucket_name, Key=self._object_key(workspace_id, storage_key))
            return True
        except Exception as exc:
            if self._is_missing_object(exc):
                return False
            raise

    def checksum(self, workspace_id: UUID, storage_key: str) -> str:
        """Return sha256 checksum for a stored R2 object."""
        stream = self.read_file(workspace_id, storage_key)
        digest = hashlib.sha256()
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()

    def _object_key(self, workspace_id: UUID, storage_key: str) -> str:
        """Build a safe object key under the workspace prefix."""
        normalized = storage_key.replace("\\", "/").lstrip("/")
        parts = [part for part in normalized.split("/") if part]
        if any(part == ".." for part in parts):
            raise ResourceConflict("Invalid storage key")
        return f"workspaces/{workspace_id}/{'/'.join(parts)}"

    def _is_missing_object(self, exc: Exception) -> bool:
        """Return whether a boto exception represents a missing object."""
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        code = str(response.get("Error", {}).get("Code", ""))
        return code in {"404", "NoSuchKey", "NotFound"}
