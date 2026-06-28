"""File storage dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.config.settings import Settings, get_settings
from server.app.database.session import get_db_session
from server.app.devices.repositories import DeviceRepository
from server.app.files.repositories import FileRepository
from server.app.files.services import FileStorageService
from server.app.files.storage import LocalStorageProvider, StorageProvider
from server.app.sync.repositories import SyncEventRepository
from server.app.workspaces.repositories import WorkspaceRepository


def get_storage_provider(settings: Annotated[Settings, Depends(get_settings)]) -> StorageProvider:
    """Create the configured storage provider."""
    return LocalStorageProvider(settings.storage_root)


def get_file_storage_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage_provider: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> FileStorageService:
    """Create file storage service."""
    return FileStorageService(
        db=db,
        file_repository=FileRepository(db),
        workspace_repository=WorkspaceRepository(db),
        device_repository=DeviceRepository(db),
        sync_repository=SyncEventRepository(db),
        storage_provider=storage_provider,
        max_upload_bytes=settings.max_upload_bytes,
    )

