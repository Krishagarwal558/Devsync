"""Safe local and remote path helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a path is unsafe for sync."""


def normalize_remote_path(path: str) -> str:
    """Normalize a remote path and reject traversal or absolute paths."""
    cleaned = path.strip().replace("\\", "/")
    if not cleaned:
        raise UnsafePathError("Path is required")
    if cleaned.startswith("/") or cleaned.startswith("\\") or ":" in cleaned:
        raise UnsafePathError("Remote path must be relative")
    parts = [part for part in cleaned.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        raise UnsafePathError("Remote path is invalid")
    return "/".join(parts)


def remote_path_for_local(root: Path, path: Path) -> str:
    """Return normalized remote path for a local path under root."""
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    try:
        relative = path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafePathError("Local path is outside the sync folder") from exc
    return normalize_remote_path(relative.as_posix())


def local_path_for_remote(root: Path, remote_path: str) -> Path:
    """Resolve a remote path under the local sync root."""
    normalized = normalize_remote_path(remote_path)
    root_resolved = root.resolve()
    destination = (root_resolved / normalized).resolve()
    try:
        destination.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafePathError("Remote path escapes local folder") from exc
    return destination


def sha256_file(path: Path) -> str:
    """Calculate sha256 for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        while True:
            chunk = input_file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

