from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .chunks import chunk_hashes_from_json, write_file_from_chunks
from .scanner import scan_workspace
from .timeutil import utc_now
from .workspace import Workspace


@dataclass(frozen=True)
class SnapshotRecord:
    id: str
    name: str
    manifest_hash: str
    created_at: str
    file_count: int


def _active_files(workspace: Workspace):
    with workspace.connect() as conn:
        return conn.execute(
            "SELECT path, size, mode, content_hash, chunk_hashes FROM files "
            "WHERE deleted=0 ORDER BY path"
        ).fetchall()


def create_snapshot(workspace: Workspace, name: str) -> SnapshotRecord:
    scan_workspace(workspace)
    rows = _active_files(workspace)
    manifest_payload = [
        {
            "path": row["path"],
            "size": row["size"],
            "mode": row["mode"],
            "content_hash": row["content_hash"],
            "chunks": json.loads(row["chunk_hashes"]),
        }
        for row in rows
    ]
    manifest_json = json.dumps(manifest_payload, sort_keys=True, separators=(",", ":"))
    manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    snapshot_id = manifest_hash[:12]
    now = utc_now()

    with workspace.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO snapshots(id, name, manifest_hash, created_at, file_count) "
            "VALUES(?, ?, ?, ?, ?)",
            (snapshot_id, name, manifest_hash, now, len(rows)),
        )
        conn.execute("DELETE FROM snapshot_files WHERE snapshot_id=?", (snapshot_id,))
        conn.executemany(
            "INSERT INTO snapshot_files(snapshot_id, path, size, mode, content_hash, chunk_hashes) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            [
                (
                    snapshot_id,
                    row["path"],
                    row["size"],
                    row["mode"],
                    row["content_hash"],
                    row["chunk_hashes"],
                )
                for row in rows
            ],
        )

    return SnapshotRecord(snapshot_id, name, manifest_hash, now, len(rows))


def list_snapshots(workspace: Workspace) -> list[SnapshotRecord]:
    with workspace.connect() as conn:
        rows = conn.execute(
            "SELECT id, name, manifest_hash, created_at, file_count FROM snapshots ORDER BY created_at DESC"
        ).fetchall()
    return [
        SnapshotRecord(row["id"], row["name"], row["manifest_hash"], row["created_at"], row["file_count"])
        for row in rows
    ]


def restore_snapshot(workspace: Workspace, snapshot_id: str, delete_extra: bool = False) -> int:
    with workspace.connect() as conn:
        snapshot = conn.execute("SELECT id FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if snapshot is None:
            raise SystemExit(f"Snapshot not found: {snapshot_id}")
        rows = conn.execute(
            "SELECT path, chunk_hashes FROM snapshot_files WHERE snapshot_id=? ORDER BY path",
            (snapshot_id,),
        ).fetchall()
        snapshot_paths = {row["path"] for row in rows}

    create_snapshot(workspace, f"before-restore-{snapshot_id}")

    restored = 0
    for row in rows:
        write_file_from_chunks(workspace, row["path"], chunk_hashes_from_json(row["chunk_hashes"]))
        restored += 1

    if delete_extra:
        with workspace.connect() as conn:
            active_paths = [
                row["path"]
                for row in conn.execute("SELECT path FROM files WHERE deleted=0").fetchall()
            ]
        for rel_path in active_paths:
            if rel_path not in snapshot_paths:
                full = workspace.root / rel_path
                if full.exists() and full.is_file():
                    full.unlink()

    scan_workspace(workspace)
    return restored

