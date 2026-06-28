"""Device dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.database.session import get_db_session
from server.app.devices.repositories import DeviceRepository
from server.app.devices.services import DeviceService


def get_device_repository(db: Annotated[AsyncSession, Depends(get_db_session)]) -> DeviceRepository:
    """Create device repository."""
    return DeviceRepository(db)


def get_device_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    repository: Annotated[DeviceRepository, Depends(get_device_repository)],
) -> DeviceService:
    """Create device service."""
    return DeviceService(db, repository)

