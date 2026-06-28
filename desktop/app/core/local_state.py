"""SQLite-backed local desktop client state."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


class LocalStateStore:
    """Stores client auth, workspace binding, checksums, queues, and activity."""

    def __init__(self, database_path: Path) -> None:
        """Create local state store."""
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_setting(self, key: str, value: str | None) -> None:
        """Save a string setting."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_setting(self, key: str) -> str | None:
        """Return a setting."""
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def save_json_setting(self, key: str, value: dict[str, object]) -> None:
        """Save JSON setting."""
        self.save_setting(key, json.dumps(value))

    def get_json_setting(self, key: str) -> dict[str, object] | None:
        """Return JSON setting."""
        value = self.get_setting(key)
        return None if value is None else json.loads(value)

    def save_known_file(
        self,
        workspace_id: UUID,
        path: str,
        checksum: str,
        file_id: str | None = None,
        version_id: str | None = None,
    ) -> None:
        """Store known checksum for a workspace path."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO known_files(workspace_id, path, checksum, file_id, version_id, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, path) DO UPDATE SET
                    checksum = excluded.checksum,
                    file_id = excluded.file_id,
                    version_id = excluded.version_id,
                    updated_at = excluded.updated_at
                """,
                (str(workspace_id), path, checksum, file_id, version_id, now),
            )

    def get_known_checksum(self, workspace_id: UUID, path: str) -> str | None:
        """Return known checksum for a path."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT checksum FROM known_files WHERE workspace_id = ? AND path = ?",
                (str(workspace_id), path),
            ).fetchone()
        return None if row is None else str(row["checksum"])

    def get_known_file(self, workspace_id: UUID, path: str) -> dict[str, str] | None:
        """Return known file metadata for a path."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT checksum, file_id, version_id FROM known_files WHERE workspace_id = ? AND path = ?",
                (str(workspace_id), path),
            ).fetchone()
        if row is None:
            return None
        return {"checksum": str(row["checksum"]), "file_id": row["file_id"], "version_id": row["version_id"]}

    def delete_known_file(self, workspace_id: UUID, path: str) -> None:
        """Delete known file state."""
        with self._connect() as connection:
            connection.execute("DELETE FROM known_files WHERE workspace_id = ? AND path = ?", (str(workspace_id), path))

    def enqueue(self, queue_name: str, workspace_id: UUID, path: str, payload: dict[str, object]) -> None:
        """Add an item to an upload/download queue."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO queues(queue_name, workspace_id, path, payload, created_at) VALUES(?, ?, ?, ?, ?)",
                (queue_name, str(workspace_id), path, json.dumps(payload), now),
            )

    def list_queue(self, queue_name: str) -> list[dict[str, object]]:
        """Return queued items."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, workspace_id, path, payload, created_at FROM queues WHERE queue_name = ? ORDER BY id ASC",
                (queue_name,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "workspace_id": row["workspace_id"],
                "path": row["path"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def remove_queue_items(self, ids: Iterable[int]) -> None:
        """Remove queue items."""
        ids_tuple = tuple(ids)
        if not ids_tuple:
            return
        placeholders = ",".join("?" for _ in ids_tuple)
        with self._connect() as connection:
            connection.execute(f"DELETE FROM queues WHERE id IN ({placeholders})", ids_tuple)

    def add_activity(self, message: str) -> None:
        """Append recent activity."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO activity(message, created_at) VALUES(?, ?)",
                (message, datetime.now(timezone.utc).isoformat()),
            )

    def recent_activity(self, limit: int = 25) -> list[str]:
        """Return recent activity messages."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT message FROM activity ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [str(row["message"]) for row in rows]

    def reset(self) -> None:
        """Clear local client state for first-run testing."""
        with self._connect() as connection:
            connection.executescript(
                """
                DELETE FROM settings;
                DELETE FROM known_files;
                DELETE FROM queues;
                DELETE FROM ignored_paths;
                DELETE FROM activity;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS known_files (
                    workspace_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    file_id TEXT,
                    version_id TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, path)
                );
                CREATE TABLE IF NOT EXISTS queues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queue_name TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ignored_paths (
                    path TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
