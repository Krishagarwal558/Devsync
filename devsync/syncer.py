from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .chunks import chunk_hashes_from_json, copy_chunks, hash_file_only, write_file_from_chunks
from .scanner import scan_workspace
from .timeutil import utc_now
from .workspace import Workspace, init_workspace


@dataclass
class SyncSummary:
    copied: int = 0
    skipped: int = 0
    conflicts: int = 0
    deleted: int = 0
    dry_run: bool = False


def _conflict_path(path: Path) -> Path:
    stamp = utc_now().replace(":", "").replace("-", "").replace("+", "Z")
    if path.suffix:
        return path.with_name(f"{path.stem}.devsync-conflict-{stamp}{path.suffix}")
    return path.with_name(f"{path.name}.devsync-conflict-{stamp}")


def _copy_incoming_from_source(source: Workspace, target: Workspace, rel_path: str, chunk_hashes: list[str]) -> None:
    copy_chunks(source, target, chunk_hashes)
    write_file_from_chunks(target, rel_path, chunk_hashes)


def sync_workspace(
    source: Workspace,
    target_path: str | Path,
    *,
    delete: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> SyncSummary:
    summary = SyncSummary(dry_run=dry_run)
    scan_workspace(source)
    target = init_workspace(target_path)

    with source.connect() as conn:
        source_files = conn.execute(
            "SELECT path, content_hash, chunk_hashes FROM files WHERE deleted=0 ORDER BY path"
        ).fetchall()

    source_paths = {row["path"] for row in source_files}

    for row in source_files:
        rel_path = row["path"]
        chunk_hashes = chunk_hashes_from_json(row["chunk_hashes"])
        target_file = target.root / rel_path

        if target_file.exists() and target_file.is_file():
            target_hash = hash_file_only(target_file)
            if target_hash == row["content_hash"]:
                summary.skipped += 1
                continue
            if not force:
                summary.conflicts += 1
                if not dry_run:
                    conflict = _conflict_path(target_file)
                    conflict.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_file, conflict)
                    _copy_incoming_from_source(source, target, rel_path, chunk_hashes)
                continue

        summary.copied += 1
        if not dry_run:
            _copy_incoming_from_source(source, target, rel_path, chunk_hashes)

    if delete:
        scan_workspace(target)
        with target.connect() as conn:
            target_files = [
                row["path"]
                for row in conn.execute("SELECT path FROM files WHERE deleted=0 ORDER BY path").fetchall()
            ]
        for rel_path in target_files:
            if rel_path in source_paths:
                continue
            full = target.root / rel_path
            if full.exists() and full.is_file():
                summary.deleted += 1
                if not dry_run:
                    os.remove(full)

    if not dry_run:
        scan_workspace(target)

    return summary

