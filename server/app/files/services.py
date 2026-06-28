"""File storage service workflows."""

from __future__ import annotations

import logging
import uuid
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.auth.models import User
from server.app.devices.models import Device
from server.app.devices.repositories import DeviceRepository
from server.app.files.models import FileVersion, StoredFile
from server.app.files.pathing import normalize_workspace_path
from server.app.files.repositories import FileRepository
from server.app.files.schemas import FileDownload, RestoreFileVersionRequest
from server.app.files.storage import StorageProvider
from server.app.sync.repositories import SyncEventRepository
from server.app.sync.models import SyncEvent
from server.app.utils.errors import PermissionDenied, ResourceConflict, ResourceNotFound
from server.app.websocket.events import realtime_dispatcher
from server.app.workspaces.models import Workspace
from server.app.workspaces.repositories import WorkspaceRepository

logger = logging.getLogger(__name__)


class FileStorageService:
    """File storage, versioning, and metadata sync workflows."""

    def __init__(
        self,
        db: AsyncSession,
        file_repository: FileRepository,
        workspace_repository: WorkspaceRepository,
        device_repository: DeviceRepository,
        sync_repository: SyncEventRepository,
        storage_provider: StorageProvider,
        max_upload_bytes: int,
    ) -> None:
        """Create file storage service."""
        self._db = db
        self._file_repository = file_repository
        self._workspace_repository = workspace_repository
        self._device_repository = device_repository
        self._sync_repository = sync_repository
        self._storage_provider = storage_provider
        self._max_upload_bytes = max_upload_bytes

    async def upload_file(
        self,
        current_user: User,
        workspace_id: UUID,
        path: str,
        sender_device_id: UUID,
        stream: object,
        checksum: str | None,
        file_type: str = "file",
    ) -> tuple[StoredFile, FileVersion]:
        """Upload a new file version and emit matching sync metadata."""
        workspace = await self._require_active_workspace(current_user, workspace_id)
        await self._require_trusted_device(current_user, sender_device_id)
        normalized_path = normalize_workspace_path(path)
        stored_file = await self._file_repository.get_by_path(workspace.id, normalized_path)
        is_new_file = stored_file is None
        if stored_file is None:
            stored_file = await self._file_repository.create_file(workspace.id, normalized_path, file_type)
        elif stored_file.deleted_at is not None:
            await self._file_repository.restore_deleted_file(stored_file)

        version_id = uuid.uuid4()
        storage_key = f"versions/{stored_file.id}/{version_id}.bin"
        try:
            metadata = self._storage_provider.save_file(workspace.id, storage_key, stream, self._max_upload_bytes)  # type: ignore[arg-type]
        except ResourceConflict:
            await self._db.rollback()
            raise
        if checksum is not None and checksum != metadata.checksum:
            self._storage_provider.delete_file(workspace.id, storage_key)
            await self._db.rollback()
            raise ResourceConflict("Checksum mismatch")

        try:
            version_number = await self._file_repository.next_version_number(stored_file.id)
            version = await self._file_repository.create_version(
                file_id=stored_file.id,
                workspace_id=workspace.id,
                created_by_device_id=sender_device_id,
                content_checksum=metadata.checksum,
                size_bytes=metadata.size_bytes,
                storage_key=storage_key,
                version_number=version_number,
                version_id=version_id,
            )
            await self._file_repository.set_current_version(stored_file, version.id)
            await self._file_repository.update_workspace_storage_usage(workspace, metadata.size_bytes)
            sync_event = await self._create_file_sync_event(
                workspace=workspace,
                sender_device_id=sender_device_id,
                event_type="file_created" if is_new_file else "file_modified",
                path=normalized_path,
                version=version,
            )
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            self._storage_provider.delete_file(workspace.id, storage_key)
            raise ResourceConflict("File version conflict") from exc

        await realtime_dispatcher.publish_sync_event(sync_event, sender_device_id=sender_device_id)
        logger.info("Uploaded file %s version %s in workspace %s", stored_file.id, version.version_number, workspace.id)
        return stored_file, version

    async def list_files(
        self,
        current_user: User,
        workspace_id: UUID,
        limit: int,
        offset: int,
        include_deleted: bool = False,
        prefix: str | None = None,
    ) -> list[StoredFile]:
        """List files in a workspace."""
        workspace = await self._require_member_workspace(current_user, workspace_id)
        normalized_prefix = normalize_workspace_path(prefix) if prefix else None
        return await self._file_repository.list_files(
            workspace.id,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
            prefix=normalized_prefix,
        )

    async def download_file(self, current_user: User, workspace_id: UUID, file_id: UUID) -> FileDownload:
        """Open the current file version for streaming."""
        workspace = await self._require_member_workspace(current_user, workspace_id)
        stored_file = await self._require_file(workspace.id, file_id)
        version = await self._file_repository.get_current_version(stored_file)
        if version is None:
            raise ResourceNotFound("File version not found")
        stream = self._storage_provider.read_file(workspace.id, version.storage_key)
        return FileDownload(
            file_name=PurePosixPath(stored_file.path).name,
            stream=stream,
            size_bytes=version.size_bytes,
            checksum=version.content_checksum,
        )

    async def delete_file(self, current_user: User, workspace_id: UUID, file_id: UUID) -> None:
        """Soft delete a file."""
        workspace = await self._require_active_workspace(current_user, workspace_id)
        stored_file = await self._require_file(workspace.id, file_id)
        await self._file_repository.soft_delete(stored_file)
        await self._db.commit()
        logger.info("Soft deleted file %s in workspace %s", file_id, workspace.id)

    async def list_versions(self, current_user: User, workspace_id: UUID, file_id: UUID) -> list[FileVersion]:
        """Return file version history."""
        workspace = await self._require_member_workspace(current_user, workspace_id)
        await self._require_file(workspace.id, file_id, include_deleted=True)
        return await self._file_repository.list_versions(workspace.id, file_id)

    async def restore_version(
        self,
        current_user: User,
        workspace_id: UUID,
        file_id: UUID,
        request: RestoreFileVersionRequest,
    ) -> tuple[StoredFile, FileVersion]:
        """Restore a previous version by creating a new latest version row."""
        workspace = await self._require_active_workspace(current_user, workspace_id)
        await self._require_trusted_device(current_user, request.sender_device_id)
        stored_file = await self._require_file(workspace.id, file_id, include_deleted=True)
        source_version = await self._file_repository.get_version(workspace.id, stored_file.id, request.version_id)
        if source_version is None:
            raise ResourceNotFound("File version not found")
        if not self._storage_provider.exists(workspace.id, source_version.storage_key):
            raise ResourceNotFound("Stored file blob not found")

        version_number = await self._file_repository.next_version_number(stored_file.id)
        restored_version = await self._file_repository.create_version(
            file_id=stored_file.id,
            workspace_id=workspace.id,
            created_by_device_id=request.sender_device_id,
            content_checksum=source_version.content_checksum,
            size_bytes=source_version.size_bytes,
            storage_key=source_version.storage_key,
            version_number=version_number,
        )
        await self._file_repository.set_current_version(stored_file, restored_version.id)
        sync_event = await self._create_file_sync_event(
            workspace=workspace,
            sender_device_id=request.sender_device_id,
            event_type="file_modified",
            path=stored_file.path,
            version=restored_version,
        )
        await self._db.commit()
        await realtime_dispatcher.publish_sync_event(sync_event, sender_device_id=request.sender_device_id)
        logger.info("Restored file %s to version %s in workspace %s", file_id, request.version_id, workspace.id)
        return stored_file, restored_version

    async def _create_file_sync_event(
        self,
        workspace: Workspace,
        sender_device_id: UUID,
        event_type: str,
        path: str,
        version: FileVersion,
    ) -> SyncEvent:
        """Create a Phase 5 metadata event in the same transaction."""
        await self._sync_repository.lock_workspace_for_sequence(workspace.id)
        sequence = await self._sync_repository.next_sequence(workspace.id)
        return await self._sync_repository.create_event(
            workspace_id=workspace.id,
            sender_device_id=sender_device_id,
            sequence=sequence,
            event_type=event_type,
            path=path,
            payload={
                "file_size": version.size_bytes,
                "metadata": {
                    "file_id": str(version.file_id),
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                },
            },
            checksum=version.content_checksum,
            bandwidth_bytes=version.size_bytes,
        )

    async def _require_member_workspace(self, current_user: User, workspace_id: UUID) -> Workspace:
        """Require active workspace membership."""
        result = await self._workspace_repository.get_visible_workspace(workspace_id, current_user.id)
        if result is None:
            raise ResourceNotFound("Workspace not found")
        return result[0]

    async def _require_active_workspace(self, current_user: User, workspace_id: UUID) -> Workspace:
        """Require active workspace membership and active workspace state."""
        workspace = await self._require_member_workspace(current_user, workspace_id)
        if workspace.status != "active" or workspace.deleted_at is not None:
            raise ResourceConflict("Workspace is not active")
        return workspace

    async def _require_trusted_device(self, current_user: User, device_id: UUID) -> Device:
        """Require an owned trusted device."""
        device = await self._device_repository.get_for_user(device_id, current_user.id)
        if device is None:
            raise ResourceNotFound("Device not found")
        if device.trust_status != "trusted" or device.deleted_at is not None:
            raise PermissionDenied("Trusted device required")
        return device

    async def _require_file(self, workspace_id: UUID, file_id: UUID, include_deleted: bool = False) -> StoredFile:
        """Require a workspace file."""
        stored_file = await self._file_repository.get_file(workspace_id, file_id, include_deleted=include_deleted)
        if stored_file is None:
            raise ResourceNotFound("File not found")
        return stored_file
