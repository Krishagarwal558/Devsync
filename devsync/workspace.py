from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .timeutil import utc_now


DEFAULT_SYNCIGNORE = """# DevSync ignore file
# Works like a small subset of .gitignore.

.devsync/
.git/
node_modules/
__pycache__/
.venv/
venv/
dist/
build/
target/
.next/
.turbo/
*.pyc
*.log
.env
.env.*
"""


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  hash TEXT PRIMARY KEY,
  size INTEGER NOT NULL,
  compressed_size INTEGER NOT NULL,
  local_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
  path TEXT PRIMARY KEY,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  mode INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  chunk_hashes TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapshots (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  manifest_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  file_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_files (
  snapshot_id TEXT NOT NULL,
  path TEXT NOT NULL,
  size INTEGER NOT NULL,
  mode INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  chunk_hashes TEXT NOT NULL,
  PRIMARY KEY (snapshot_id, path),
  FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  path TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that closes when used as a context manager."""

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        """Commit or roll back, then close the connection."""
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return bool(result)


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def meta_dir(self) -> Path:
        return self.root / ".devsync"

    @property
    def db_path(self) -> Path:
        return self.meta_dir / "devsync.sqlite"

    @property
    def chunks_dir(self) -> Path:
        return self.meta_dir / "chunks"

    @property
    def syncignore_path(self) -> Path:
        return self.root / ".syncignore"

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, factory=ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def find_workspace(path: str | Path) -> Workspace:
    current = resolve_path(path)
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".devsync" / "devsync.sqlite").exists():
            return Workspace(candidate)
    raise SystemExit(f"No DevSync workspace found at or above: {current}")


def init_workspace(path: str | Path, name: str | None = None) -> Workspace:
    root = resolve_path(path)
    root.mkdir(parents=True, exist_ok=True)
    workspace = Workspace(root)
    workspace.meta_dir.mkdir(parents=True, exist_ok=True)
    workspace.chunks_dir.mkdir(parents=True, exist_ok=True)

    with workspace.connect() as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute("SELECT value FROM meta WHERE key='workspace_id'").fetchone()
        if existing is None:
            conn.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("workspace_id", str(uuid.uuid4())))
            conn.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("created_at", utc_now()))
            conn.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("schema_version", "1"))
        if name:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES('name', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (name,),
            )

    if not workspace.syncignore_path.exists():
        workspace.syncignore_path.write_text(DEFAULT_SYNCIGNORE, encoding="utf-8")

    return workspace


def ensure_workspace(path: str | Path) -> Workspace:
    workspace = find_workspace(path)
    workspace.chunks_dir.mkdir(parents=True, exist_ok=True)
    with workspace.connect() as conn:
        conn.executescript(SCHEMA)
    return workspace
