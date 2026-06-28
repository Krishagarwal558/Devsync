from __future__ import annotations

import io
import uuid

import pytest

from server.app.files.storage import LocalStorageProvider
from server.app.utils.errors import ResourceConflict


def test_storage_rejects_upload_too_large(tmp_path) -> None:  # type: ignore[no-untyped-def]
    provider = LocalStorageProvider(tmp_path)

    with pytest.raises(ResourceConflict):
        provider.save_file(uuid.uuid4(), "versions/file/version.bin", io.BytesIO(b"12345"), max_bytes=4)

