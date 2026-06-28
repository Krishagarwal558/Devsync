from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone

import pytest

from server.app.auth.models import User
from server.app.devices.models import Device
from server.app.files.models import FileVersion, StoredFile
from server.app.files.repositories import FileRepository
from server.app.files.schemas import RestoreFileVersionRequest
from server.app.files.services import FileStorageService
from server.app.files.storage import LocalStorageProvider
from server.app.sync.models import SyncEvent
from server.app.utils.errors import PermissionDenied, ResourceConflict
from server.app.workspaces.models import Workspace, WorkspaceMember


class UnitOfWorkStub:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class WorkspaceRepositoryStub:
    def __init__(self, workspace: Workspace, membership: WorkspaceMember) -> None:
        self.workspace = workspace
        self.membership = membership

    async def get_visible_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Workspace, WorkspaceMember] | None:
        if self.workspace.id == workspace_id and self.membership.user_id == user_id:
            return self.workspace, self.membership
        return None


class DeviceRepositoryStub:
    def __init__(self, device: Device) -> None:
        self.device = device

    async def get_for_user(self, device_id: uuid.UUID, user_id: uuid.UUID, include_deleted: bool = False) -> Device | None:
        if self.device.id == device_id and self.device.user_id == user_id:
            return self.device
        return None


class FileRepositoryStub:
    def __init__(self) -> None:
        self.files: dict[uuid.UUID, StoredFile] = {}
        self.versions: dict[uuid.UUID, FileVersion] = {}

    async def get_by_path(self, workspace_id: uuid.UUID, path: str) -> StoredFile | None:
        return next((file for file in self.files.values() if file.workspace_id == workspace_id and file.path == path), None)

    async def get_file(self, workspace_id: uuid.UUID, file_id: uuid.UUID, include_deleted: bool = False) -> StoredFile | None:
        stored_file = self.files.get(file_id)
        if stored_file is None or stored_file.workspace_id != workspace_id:
            return None
        if stored_file.deleted_at is not None and not include_deleted:
            return None
        return stored_file

    async def create_file(self, workspace_id: uuid.UUID, path: str, file_type: str) -> StoredFile:
        now = datetime.now(timezone.utc)
        stored_file = StoredFile(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            path=path,
            file_type=file_type,
            current_version_id=None,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        self.files[stored_file.id] = stored_file
        return stored_file

    async def restore_deleted_file(self, stored_file: StoredFile) -> StoredFile:
        stored_file.deleted_at = None
        return stored_file

    async def next_version_number(self, file_id: uuid.UUID) -> int:
        numbers = [version.version_number for version in self.versions.values() if version.file_id == file_id]
        return max(numbers, default=0) + 1

    async def create_version(
        self,
        file_id: uuid.UUID,
        workspace_id: uuid.UUID,
        created_by_device_id: uuid.UUID,
        content_checksum: str,
        size_bytes: int,
        storage_key: str,
        version_number: int,
        version_id: uuid.UUID | None = None,
    ) -> FileVersion:
        version = FileVersion(
            id=version_id or uuid.uuid4(),
            file_id=file_id,
            workspace_id=workspace_id,
            created_by_device_id=created_by_device_id,
            content_checksum=content_checksum,
            size_bytes=size_bytes,
            storage_key=storage_key,
            version_number=version_number,
            created_at=datetime.now(timezone.utc),
        )
        self.versions[version.id] = version
        return version

    async def set_current_version(self, stored_file: StoredFile, version_id: uuid.UUID) -> StoredFile:
        stored_file.current_version_id = version_id
        stored_file.deleted_at = None
        return stored_file

    async def list_files(
        self,
        workspace_id: uuid.UUID,
        limit: int,
        offset: int,
        include_deleted: bool = False,
        prefix: str | None = None,
    ) -> list[StoredFile]:
        files = [file for file in self.files.values() if file.workspace_id == workspace_id]
        if not include_deleted:
            files = [file for file in files if file.deleted_at is None]
        if prefix is not None:
            files = [file for file in files if file.path.startswith(prefix)]
        return sorted(files, key=lambda file: file.path)[offset : offset + limit]

    async def get_version(self, workspace_id: uuid.UUID, file_id: uuid.UUID, version_id: uuid.UUID) -> FileVersion | None:
        version = self.versions.get(version_id)
        if version and version.workspace_id == workspace_id and version.file_id == file_id:
            return version
        return None

    async def get_current_version(self, stored_file: StoredFile) -> FileVersion | None:
        return self.versions.get(stored_file.current_version_id)

    async def list_versions(self, workspace_id: uuid.UUID, file_id: uuid.UUID) -> list[FileVersion]:
        versions = [version for version in self.versions.values() if version.workspace_id == workspace_id and version.file_id == file_id]
        return sorted(versions, key=lambda version: version.version_number, reverse=True)

    async def soft_delete(self, stored_file: StoredFile) -> StoredFile:
        stored_file.deleted_at = datetime.now(timezone.utc)
        return stored_file

    async def update_workspace_storage_usage(self, workspace: Workspace, delta_bytes: int) -> Workspace:
        settings = dict(workspace.settings or {})
        settings["storage_usage_bytes"] = int(settings.get("storage_usage_bytes", 0)) + delta_bytes
        workspace.settings = settings
        return workspace


class SyncRepositoryStub:
    def __init__(self) -> None:
        self.events: list[SyncEvent] = []

    async def lock_workspace_for_sequence(self, workspace_id: uuid.UUID) -> None:
        return None

    async def next_sequence(self, workspace_id: uuid.UUID) -> int:
        return len([event for event in self.events if event.workspace_id == workspace_id]) + 1

    async def create_event(
        self,
        workspace_id: uuid.UUID,
        sender_device_id: uuid.UUID,
        sequence: int,
        event_type: str,
        path: str,
        payload: dict[str, object],
        checksum: str | None,
        bandwidth_bytes: int,
    ) -> SyncEvent:
        event = SyncEvent(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            sender_device_id=sender_device_id,
            sequence=sequence,
            event_type=event_type,
            path=path,
            payload=payload,
            checksum=checksum,
            bandwidth_bytes=bandwidth_bytes,
            status="accepted",
            created_at=datetime.now(timezone.utc),
        )
        self.events.append(event)
        return event


def make_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="owner@example.com",
        display_name="Owner",
        password_hash="hash",
        status="active",
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


def make_workspace(user: User) -> tuple[Workspace, WorkspaceMember]:
    now = datetime.now(timezone.utc)
    workspace = Workspace(
        id=uuid.uuid4(),
        owner_id=user.id,
        name="Project",
        slug="project",
        status="active",
        settings={},
        archived_at=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        status="active",
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    return workspace, membership


def make_device(user: User, trust_status: str = "trusted") -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Laptop",
        platform="windows",
        public_key="key",
        trust_status=trust_status,
        last_seen_at=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


def make_service(tmp_path, trust_status: str = "trusted"):  # type: ignore[no-untyped-def]
    user = make_user()
    workspace, membership = make_workspace(user)
    device = make_device(user, trust_status)
    db = UnitOfWorkStub()
    file_repo = FileRepositoryStub()
    sync_repo = SyncRepositoryStub()
    service = FileStorageService(
        db,  # type: ignore[arg-type]
        file_repo,  # type: ignore[arg-type]
        WorkspaceRepositoryStub(workspace, membership),  # type: ignore[arg-type]
        DeviceRepositoryStub(device),  # type: ignore[arg-type]
        sync_repo,  # type: ignore[arg-type]
        LocalStorageProvider(tmp_path),
        max_upload_bytes=1024 * 1024,
    )
    return service, user, workspace, device, file_repo, sync_repo, db


@pytest.mark.anyio
async def test_upload_creates_file_version_and_sync_event(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, user, workspace, device, file_repo, sync_repo, db = make_service(tmp_path)
    content = b"hello"

    stored_file, version = await service.upload_file(
        user,
        workspace.id,
        "src/app.py",
        device.id,
        io.BytesIO(content),
        checksum=hashlib.sha256(content).hexdigest(),
    )

    assert stored_file.current_version_id == version.id
    assert version.version_number == 1
    assert version.size_bytes == len(content)
    assert workspace.settings["storage_usage_bytes"] == len(content)
    assert sync_repo.events[0].event_type == "file_created"
    assert sync_repo.events[0].payload["metadata"]["version_id"] == str(version.id)  # type: ignore[index]
    assert file_repo.versions[version.id] == version
    assert db.committed


@pytest.mark.anyio
async def test_upload_rejects_checksum_mismatch(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, user, workspace, device, _, _, db = make_service(tmp_path)

    with pytest.raises(ResourceConflict):
        await service.upload_file(user, workspace.id, "file.txt", device.id, io.BytesIO(b"content"), checksum="wrong")

    assert db.rolled_back


@pytest.mark.anyio
async def test_upload_requires_trusted_device(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, user, workspace, device, _, _, _ = make_service(tmp_path, trust_status="pending")

    with pytest.raises(PermissionDenied):
        await service.upload_file(user, workspace.id, "file.txt", device.id, io.BytesIO(b"content"), checksum=None)


@pytest.mark.anyio
async def test_upload_blocks_revoked_device(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, user, workspace, device, _, _, _ = make_service(tmp_path, trust_status="revoked")

    with pytest.raises(PermissionDenied):
        await service.upload_file(user, workspace.id, "file.txt", device.id, io.BytesIO(b"content"), checksum=None)


@pytest.mark.anyio
async def test_restore_version_creates_new_latest_metadata_version(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, user, workspace, device, _, _, _ = make_service(tmp_path)
    first_file, first_version = await service.upload_file(user, workspace.id, "file.txt", device.id, io.BytesIO(b"one"), checksum=None)
    await service.upload_file(user, workspace.id, "file.txt", device.id, io.BytesIO(b"two"), checksum=None)

    restored_file, restored_version = await service.restore_version(
        user,
        workspace.id,
        first_file.id,
        RestoreFileVersionRequest(version_id=first_version.id, sender_device_id=device.id),
    )

    assert restored_file.current_version_id == restored_version.id
    assert restored_version.version_number == 3
    assert restored_version.storage_key == first_version.storage_key

@pytest.mark.anyio
async def test_soft_delete_hides_file_from_default_list(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service, user, workspace, device, _, _, _ = make_service(tmp_path)
    stored_file, _ = await service.upload_file(user, workspace.id, "file.txt", device.id, io.BytesIO(b"one"), checksum=None)

    await service.delete_file(user, workspace.id, stored_file.id)

    assert await service.list_files(user, workspace.id, limit=10, offset=0) == []
    assert len(await service.list_files(user, workspace.id, limit=10, offset=0, include_deleted=True)) == 1
