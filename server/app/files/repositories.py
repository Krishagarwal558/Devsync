"""File metadata repository."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.files.models import FileVersion, StoredFile
from server.app.workspaces.models import Workspace


class FileRepository:
    """Database access for files and file versions."""

    def __init__(self, session: AsyncSession) -> None:
        """Create repository."""
        self._session = session

    async def get_by_path(self, workspace_id: UUID, path: str) -> StoredFile | None:
        """Return a file by workspace path."""
        statement: Select[tuple[StoredFile]] = select(StoredFile).where(
            StoredFile.workspace_id == workspace_id,
            StoredFile.path == path,
        )
        return await self._session.scalar(statement)

    async def get_file(self, workspace_id: UUID, file_id: UUID, include_deleted: bool = False) -> StoredFile | None:
        """Return a file by id."""
        statement: Select[tuple[StoredFile]] = select(StoredFile).where(
            StoredFile.workspace_id == workspace_id,
            StoredFile.id == file_id,
        )
        if not include_deleted:
            statement = statement.where(StoredFile.deleted_at.is_(None))
        return await self._session.scalar(statement)

    async def create_file(self, workspace_id: UUID, path: str, file_type: str) -> StoredFile:
        """Create file metadata."""
        stored_file = StoredFile(workspace_id=workspace_id, path=path, file_type=file_type)
        self._session.add(stored_file)
        await self._session.flush()
        await self._session.refresh(stored_file)
        return stored_file

    async def restore_deleted_file(self, stored_file: StoredFile) -> StoredFile:
        """Clear soft delete marker."""
        stored_file.deleted_at = None
        await self._session.flush()
        await self._session.refresh(stored_file)
        return stored_file

    async def next_version_number(self, file_id: UUID) -> int:
        """Return next file-local version number."""
        statement = select(func.coalesce(func.max(FileVersion.version_number), 0) + 1).where(FileVersion.file_id == file_id)
        return int(await self._session.scalar(statement))

    async def create_version(
        self,
        file_id: UUID,
        workspace_id: UUID,
        created_by_device_id: UUID,
        content_checksum: str,
        size_bytes: int,
        storage_key: str,
        version_number: int,
        version_id: UUID | None = None,
    ) -> FileVersion:
        """Create immutable file version metadata."""
        version = FileVersion(
            file_id=file_id,
            workspace_id=workspace_id,
            created_by_device_id=created_by_device_id,
            content_checksum=content_checksum,
            size_bytes=size_bytes,
            storage_key=storage_key,
            version_number=version_number,
            created_at=datetime.now(timezone.utc),
        )
        if version_id is not None:
            version.id = version_id
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def set_current_version(self, stored_file: StoredFile, version_id: UUID) -> StoredFile:
        """Point a file at its current version."""
        stored_file.current_version_id = version_id
        stored_file.deleted_at = None
        await self._session.flush()
        await self._session.refresh(stored_file)
        return stored_file

    async def list_files(
        self,
        workspace_id: UUID,
        limit: int,
        offset: int,
        include_deleted: bool = False,
        prefix: str | None = None,
    ) -> list[StoredFile]:
        """Return workspace files."""
        statement: Select[tuple[StoredFile]] = (
            select(StoredFile)
            .where(StoredFile.workspace_id == workspace_id)
            .order_by(StoredFile.path.asc())
            .limit(limit)
            .offset(offset)
        )
        if not include_deleted:
            statement = statement.where(StoredFile.deleted_at.is_(None))
        if prefix is not None:
            statement = statement.where(StoredFile.path.startswith(prefix))
        return list((await self._session.scalars(statement)).all())

    async def get_version(self, workspace_id: UUID, file_id: UUID, version_id: UUID) -> FileVersion | None:
        """Return a specific file version."""
        statement: Select[tuple[FileVersion]] = select(FileVersion).where(
            FileVersion.workspace_id == workspace_id,
            FileVersion.file_id == file_id,
            FileVersion.id == version_id,
        )
        return await self._session.scalar(statement)

    async def get_current_version(self, stored_file: StoredFile) -> FileVersion | None:
        """Return current file version."""
        if stored_file.current_version_id is None:
            return None
        statement: Select[tuple[FileVersion]] = select(FileVersion).where(FileVersion.id == stored_file.current_version_id)
        return await self._session.scalar(statement)

    async def list_versions(self, workspace_id: UUID, file_id: UUID) -> list[FileVersion]:
        """Return version history."""
        statement: Select[tuple[FileVersion]] = (
            select(FileVersion)
            .where(FileVersion.workspace_id == workspace_id, FileVersion.file_id == file_id)
            .order_by(FileVersion.version_number.desc())
        )
        return list((await self._session.scalars(statement)).all())

    async def soft_delete(self, stored_file: StoredFile) -> StoredFile:
        """Soft delete a file."""
        stored_file.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(stored_file)
        return stored_file

    async def update_workspace_storage_usage(self, workspace: Workspace, delta_bytes: int) -> Workspace:
        """Update workspace storage usage in settings."""
        settings = dict(workspace.settings or {})
        current = int(settings.get("storage_usage_bytes", 0))
        settings["storage_usage_bytes"] = max(current + delta_bytes, 0)
        workspace.settings = settings
        await self._session.flush()
        await self._session.refresh(workspace)
        return workspace
