"""Safe workspace file path helpers."""

from __future__ import annotations

from server.app.utils.errors import ResourceConflict


def normalize_workspace_path(path: str) -> str:
    """Return a normalized relative path or raise for unsafe paths."""
    cleaned = path.strip().replace("\\", "/")
    if not cleaned:
        raise ResourceConflict("Path is required")
    if cleaned.startswith("/") or cleaned.startswith("\\") or ":" in cleaned:
        raise ResourceConflict("Path must be relative")
    parts = [part for part in cleaned.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        raise ResourceConflict("Path is invalid")
    return "/".join(parts)

