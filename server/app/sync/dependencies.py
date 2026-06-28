"""Synchronization dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.database.session import get_db_session
from server.app.devices.repositories import DeviceRepository
from server.app.sync.repositories import SyncEventRepository
from server.app.sync.services import SyncEventService
from server.app.workspaces.repositories import WorkspaceRepository


def get_sync_event_repository(db: Annotated[AsyncSession, Depends(get_db_session)]) -> SyncEventRepository:
    """Create sync event repository."""
    return SyncEventRepository(db)


def get_sync_event_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    sync_repository: Annotated[SyncEventRepository, Depends(get_sync_event_repository)],
) -> SyncEventService:
    """Create sync event service."""
    return SyncEventService(
        db=db,
        sync_repository=sync_repository,
        workspace_repository=WorkspaceRepository(db),
        device_repository=DeviceRepository(db),
    )

