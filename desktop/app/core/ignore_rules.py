"""Ignore rules for local sync."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from desktop.app.core.path_utils import UnsafePathError, remote_path_for_local


DEFAULT_IGNORES = (
    ".devsync/",
    "node_modules/",
    ".venv/",
    "__pycache__/",
    "dist/",
    "build/",
    "target/",
    ".git/",
    "*.log",
)


class IgnoreRules:
    """Path ignore matcher."""

    def __init__(self, patterns: tuple[str, ...] = DEFAULT_IGNORES) -> None:
        """Create matcher."""
        self._patterns = patterns

    def is_ignored_remote_path(self, remote_path: str) -> bool:
        """Return whether a remote path should be ignored."""
        normalized = remote_path.strip().replace("\\", "/")
        segments = normalized.split("/")
        for pattern in self._patterns:
            if pattern.endswith("/"):
                folder = pattern.rstrip("/")
                if folder in segments:
                    return True
            elif fnmatch(normalized, pattern) or any(fnmatch(segment, pattern) for segment in segments):
                return True
        return False

    def is_ignored_local_path(self, root: Path, path: Path) -> bool:
        """Return whether a local path should be ignored."""
        try:
            remote_path = remote_path_for_local(root, path)
        except UnsafePathError:
            return True
        return self.is_ignored_remote_path(remote_path)

