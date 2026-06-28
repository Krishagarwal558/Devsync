from __future__ import annotations

from uuid import uuid4

import pytest

from server.app.files.storage import R2StorageProvider
from server.app.utils.errors import ResourceConflict


def test_r2_object_key_scopes_under_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(R2StorageProvider, "__init__", lambda self, *args, **kwargs: None)
    provider = R2StorageProvider("endpoint", "bucket", "key", "secret")
    workspace_id = uuid4()

    key = provider._object_key(workspace_id, "versions/file-id/version-id.bin")  # type: ignore[attr-defined]

    assert key == f"workspaces/{workspace_id}/versions/file-id/version-id.bin"


def test_r2_object_key_rejects_path_traversal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(R2StorageProvider, "__init__", lambda self, *args, **kwargs: None)
    provider = R2StorageProvider("endpoint", "bucket", "key", "secret")

    with pytest.raises(ResourceConflict):
        provider._object_key(uuid4(), "../secrets.bin")  # type: ignore[attr-defined]
