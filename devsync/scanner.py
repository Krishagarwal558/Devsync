from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from .chunks import DEFAULT_CHUNK_SIZE, chunk_hashes_to_json, store_file
from .ignore import IgnoreMatcher
from .timeutil import utc_now
from .workspace import Workspace


@dataclass
class ScanSummary:
    added: int = 0
    modified: int = 0
    deleted: int = 0
    unchanged: int = 0
    files_seen: int = 0
    bytes_indexed: int = 0

    @property
    def changed(self) -> int:
        return self.added + self.modified + self.deleted


def iter_workspace_files(workspace: Workspace):
    matcher = IgnoreMatcher.from_workspace(workspace.root)
    for dirpath, dirnames, filenames in os.walk(workspace.root):
        base = Path(dirpath)
        rel_dir = base.relative_to(workspace.root).as_posix()
        if rel_dir == ".":
            rel_dir = ""

        kept_dirs = []
        for dirname in dirnames:
            rel = f"{rel_dir}/{dirname}".strip("/")
            full = base / dirname
            if full.is_symlink() or matcher.ignored(rel, is_dir=True):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            full = base / filename
            if full.is_symlink():
                continue
            rel = f"{rel_dir}/{filename}".strip("/")
            if matcher.ignored(rel, is_dir=False):
                continue
            yield rel, full


def scan_workspace(workspace: Workspace, chunk_size: int = DEFAULT_CHUNK_SIZE) -> ScanSummary:
    summary = ScanSummary()
    now = utc_now()

    with workspace.connect() as conn:
        previous = {
            row["path"]: row
            for row in conn.execute("SELECT * FROM files WHERE deleted=0").fetchall()
        }

    current_paths: set[str] = set()

    for rel_path, full_path in iter_workspace_files(workspace):
        stat = full_path.stat()
        current_paths.add(rel_path)
        summary.files_seen += 1

        old = previous.get(rel_path)
        if old and old["mtime_ns"] == stat.st_mtime_ns and old["size"] == stat.st_size:
            summary.unchanged += 1
            continue

        content_hash, chunk_hashes = store_file(workspace, full_path, chunk_size=chunk_size)
        chunk_json = chunk_hashes_to_json(chunk_hashes)
        summary.bytes_indexed += stat.st_size

        if old is None:
            summary.added += 1
            event_kind = "file.added"
        elif old["content_hash"] != content_hash:
            summary.modified += 1
            event_kind = "file.modified"
        else:
            summary.unchanged += 1
            event_kind = "file.metadata_changed"

        with workspace.connect() as conn:
            conn.execute(
                "INSERT INTO files(path, size, mtime_ns, mode, content_hash, chunk_hashes, updated_at, deleted) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, 0) "
                "ON CONFLICT(path) DO UPDATE SET "
                "size=excluded.size, mtime_ns=excluded.mtime_ns, mode=excluded.mode, "
                "content_hash=excluded.content_hash, chunk_hashes=excluded.chunk_hashes, "
                "updated_at=excluded.updated_at, deleted=0",
                (
                    rel_path,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stat.st_mode,
                    content_hash,
                    chunk_json,
                    now,
                ),
            )
            if event_kind != "file.metadata_changed":
                conn.execute(
                    "INSERT INTO events(id, kind, path, payload, created_at) VALUES(?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        event_kind,
                        rel_path,
                        json.dumps({"content_hash": content_hash}, separators=(",", ":")),
                        now,
                    ),
                )

    missing_paths = set(previous) - current_paths
    if missing_paths:
        with workspace.connect() as conn:
            for rel_path in sorted(missing_paths):
                summary.deleted += 1
                conn.execute(
                    "UPDATE files SET deleted=1, updated_at=? WHERE path=?",
                    (now, rel_path),
                )
                conn.execute(
                    "INSERT INTO events(id, kind, path, payload, created_at) VALUES(?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), "file.deleted", rel_path, "{}", now),
                )

    return summary


def workspace_status(workspace: Workspace) -> dict[str, int | str | None]:
    with workspace.connect() as conn:
        active_files = conn.execute("SELECT COUNT(*) FROM files WHERE deleted=0").fetchone()[0]
        deleted_files = conn.execute("SELECT COUNT(*) FROM files WHERE deleted=1").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        snapshots = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        total_bytes = conn.execute("SELECT COALESCE(SUM(size), 0) FROM files WHERE deleted=0").fetchone()[0]
        workspace_id = conn.execute("SELECT value FROM meta WHERE key='workspace_id'").fetchone()
        name = conn.execute("SELECT value FROM meta WHERE key='name'").fetchone()

    return {
        "workspace_id": workspace_id[0] if workspace_id else None,
        "name": name[0] if name else None,
        "active_files": active_files,
        "deleted_files": deleted_files,
        "chunks": chunks,
        "snapshots": snapshots,
        "tracked_bytes": total_bytes,
    }

