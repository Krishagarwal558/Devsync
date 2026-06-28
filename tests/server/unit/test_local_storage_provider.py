from __future__ import annotations

import hashlib
import io
import uuid

import pytest

from server.app.files.storage import LocalStorageProvider
from server.app.utils.errors import ResourceConflict


def test_local_storage_provider_saves_reads_checksums_and_deletes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    provider = LocalStorageProvider(tmp_path)
    workspace_id = uuid.uuid4()
    content = b"hello devsync"
    storage_key = f"versions/{uuid.uuid4()}/{uuid.uuid4()}.bin"

    metadata = provider.save_file(workspace_id, storage_key, io.BytesIO(content), max_bytes=1024)

    assert metadata.size_bytes == len(content)
    assert metadata.checksum == hashlib.sha256(content).hexdigest()
    assert provider.exists(workspace_id, storage_key)
    assert provider.read_file(workspace_id, storage_key).read() == content
    assert provider.checksum(workspace_id, storage_key) == metadata.checksum

    provider.delete_file(workspace_id, storage_key)

    assert not provider.exists(workspace_id, storage_key)


def test_local_storage_provider_enforces_size_limit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    provider = LocalStorageProvider(tmp_path)

    with pytest.raises(ResourceConflict):
        provider.save_file(uuid.uuid4(), "versions/file/version.bin", io.BytesIO(b"too large"), max_bytes=3)


def test_local_storage_provider_rejects_traversal_keys(tmp_path) -> None:  # type: ignore[no-untyped-def]
    provider = LocalStorageProvider(tmp_path)

    with pytest.raises(ResourceConflict):
        provider.save_file(uuid.uuid4(), "../../escape.bin", io.BytesIO(b"escape"), max_bytes=1024)
