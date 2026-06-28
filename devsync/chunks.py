from __future__ import annotations

import hashlib
import json
import os
import zlib
from pathlib import Path

from .timeutil import utc_now
from .workspace import Workspace

DEFAULT_CHUNK_SIZE = 1024 * 1024


class ChunkStore:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.workspace.chunks_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, chunk_hash: str) -> Path:
        return self.workspace.chunks_dir / chunk_hash[:2] / chunk_hash[2:4] / f"{chunk_hash}.chunk"

    def put(self, raw: bytes) -> tuple[str, int, int, str]:
        chunk_hash = hashlib.sha256(raw).hexdigest()
        target = self.path_for(chunk_hash)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            compressed = zlib.compress(raw, level=6)
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(compressed)
            os.replace(tmp, target)

        compressed_size = target.stat().st_size
        rel = target.relative_to(self.workspace.meta_dir).as_posix()
        return chunk_hash, len(raw), compressed_size, rel

    def read(self, chunk_hash: str) -> bytes:
        path = self.path_for(chunk_hash)
        if not path.exists():
            raise FileNotFoundError(f"Missing chunk {chunk_hash}")
        return zlib.decompress(path.read_bytes())


def hash_file_only(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def store_file(
    workspace: Workspace,
    path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> tuple[str, list[str]]:
    store = ChunkStore(workspace)
    digest = hashlib.sha256()
    chunk_hashes: list[str] = []

    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
            chunk_hash, size, compressed_size, local_path = store.put(block)
            chunk_hashes.append(chunk_hash)
            with workspace.connect() as conn:
                conn.execute(
                    "INSERT INTO chunks(hash, size, compressed_size, local_path, created_at) "
                    "VALUES(?, ?, ?, ?, ?) "
                    "ON CONFLICT(hash) DO NOTHING",
                    (chunk_hash, size, compressed_size, local_path, utc_now()),
                )

    return digest.hexdigest(), chunk_hashes


def write_file_from_chunks(workspace: Workspace, rel_path: str, chunk_hashes: list[str]) -> None:
    target = workspace.root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.devsync-tmp")
    store = ChunkStore(workspace)

    with tmp.open("wb") as handle:
        for chunk_hash in chunk_hashes:
            handle.write(store.read(chunk_hash))

    os.replace(tmp, target)


def copy_chunks(
    source: Workspace,
    target: Workspace,
    chunk_hashes: list[str],
) -> None:
    source_store = ChunkStore(source)
    target_store = ChunkStore(target)

    with target.connect() as conn:
        for chunk_hash in chunk_hashes:
            raw = source_store.read(chunk_hash)
            copied_hash, size, compressed_size, local_path = target_store.put(raw)
            if copied_hash != chunk_hash:
                raise RuntimeError(f"Chunk hash mismatch while copying {chunk_hash}")
            conn.execute(
                "INSERT INTO chunks(hash, size, compressed_size, local_path, created_at) "
                "VALUES(?, ?, ?, ?, ?) "
                "ON CONFLICT(hash) DO NOTHING",
                (chunk_hash, size, compressed_size, local_path, utc_now()),
            )


def chunk_hashes_to_json(chunk_hashes: list[str]) -> str:
    return json.dumps(chunk_hashes, separators=(",", ":"))


def chunk_hashes_from_json(value: str) -> list[str]:
    loaded = json.loads(value)
    if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
        raise ValueError("Invalid chunk hash list")
    return loaded

