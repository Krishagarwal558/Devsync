from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest

from desktop.app.core.local_state import LocalStateStore
from desktop.app.services.sync_service import DesktopSyncService


class FakeFileClient:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.downloads: dict[str, bytes] = {}
        self.fail_upload = False

    async def upload_file(self, workspace_id: str, device_id: str, local_file: Path, remote_path: str, checksum: str) -> dict[str, object]:
        if self.fail_upload:
            raise RuntimeError("network down")
        self.uploaded.append((remote_path, checksum))
        return {
            "file_id": str(uuid.uuid4()),
            "version_id": str(uuid.uuid4()),
            "path": remote_path,
            "checksum": checksum,
            "size_bytes": local_file.stat().st_size,
        }

    async def download_file(self, workspace_id: str, file_id: str) -> bytes:
        return self.downloads[file_id]

    async def delete_file(self, workspace_id: str, file_id: str) -> None:
        self.deleted.append(file_id)


def make_service(tmp_path):  # type: ignore[no-untyped-def]
    state = LocalStateStore(tmp_path / "state.sqlite")
    workspace_id = uuid.uuid4()
    device_id = uuid.uuid4()
    root = tmp_path / "workspace"
    root.mkdir()
    state.save_setting("workspace_id", str(workspace_id))
    state.save_setting("device_id", str(device_id))
    state.save_setting("local_folder_path", str(root))
    client = FakeFileClient()
    service = DesktopSyncService(state, client, "http://localhost:8000", "token", remote_apply_seconds=60)
    return service, state, client, workspace_id, root


@pytest.mark.anyio
async def test_upload_changed_file_skips_known_checksum_and_remote_applying(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, state, client, workspace_id, root = make_service(tmp_path)
    local_file = root / "src" / "app.py"
    local_file.parent.mkdir()
    local_file.write_text("one", encoding="utf-8")
    checksum = hashlib.sha256(b"one").hexdigest()

    first = await service.upload_changed_file(local_file)
    state.save_known_file(workspace_id, "src/app.py", checksum)
    second = await service.upload_changed_file(local_file)
    service.mark_remote_applying("src/app.py")
    local_file.write_text("two", encoding="utf-8")
    third = await service.upload_changed_file(local_file)

    assert first is not None
    assert second is None
    assert third is None
    assert len(client.uploaded) == 1


def test_apply_remote_file_writes_temp_then_replaces_and_updates_checksum(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, state, _, workspace_id, root = make_service(tmp_path)
    destination = root / "src" / "app.py"

    service.apply_remote_file(destination, "src/app.py", b"remote", "remote-checksum")

    assert destination.read_bytes() == b"remote"
    assert state.get_known_checksum(workspace_id, "src/app.py") == "remote-checksum"


def test_apply_remote_file_creates_conflict_copies(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, state, _, workspace_id, root = make_service(tmp_path)
    destination = root / "src" / "app.py"
    destination.parent.mkdir()
    destination.write_text("local-old", encoding="utf-8")
    state.save_known_file(workspace_id, "src/app.py", hashlib.sha256(b"known").hexdigest())

    service.apply_remote_file(destination, "src/app.py", b"remote-new", "remote-checksum")

    assert destination.with_name("app.py.LOCAL-CONFLICT").exists()
    assert destination.with_name("app.py.REMOTE-CONFLICT").read_bytes() == b"remote-new"


@pytest.mark.anyio
async def test_handle_local_deleted_file_soft_deletes_cloud_and_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, state, client, workspace_id, root = make_service(tmp_path)
    path = root / "src" / "app.py"
    path.parent.mkdir()
    file_id = str(uuid.uuid4())
    state.save_known_file(workspace_id, "src/app.py", "abc", file_id=file_id)

    await service.handle_local_deleted_file(path)

    assert client.deleted == [file_id]
    assert state.get_known_file(workspace_id, "src/app.py") is None


@pytest.mark.anyio
async def test_retry_queue_replays_failed_upload(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, state, client, _, root = make_service(tmp_path)
    local_file = root / "src" / "app.py"
    local_file.parent.mkdir()
    local_file.write_text("retry me", encoding="utf-8")
    client.fail_upload = True

    with pytest.raises(RuntimeError):
        await service.upload_changed_file(local_file)

    assert len(state.list_queue("upload")) == 1
    client.fail_upload = False
    uploads, downloads = await service.retry_pending()

    assert (uploads, downloads) == (1, 0)
    assert state.list_queue("upload") == []
