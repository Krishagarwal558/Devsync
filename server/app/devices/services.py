"""Device service workflows."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from server.app.auth.models import User
from server.app.devices.models import Device
from server.app.devices.repositories import DeviceRepository
from server.app.devices.schemas import RegisterDeviceRequest, UpdateDeviceRequest
from server.app.utils.errors import ResourceConflict, ResourceNotFound

logger = logging.getLogger(__name__)


class DeviceService:
    """Device management use cases."""

    def __init__(self, db: AsyncSession, repository: DeviceRepository) -> None:
        """Create device service."""
        self._db = db
        self._repository = repository

    async def register_device(self, current_user: User, request: RegisterDeviceRequest) -> Device:
        """Register a new pending device for the current user."""
        device = await self._repository.create_device(
            user_id=current_user.id,
            name=request.name,
            platform=request.platform,
            public_key=request.public_key,
        )
        await self._db.commit()
        logger.info("Registered device %s for user %s", device.id, current_user.id)
        return device

    async def list_devices(
        self,
        current_user: User,
        include_revoked: bool = False,
        include_deleted: bool = False,
    ) -> list[Device]:
        """List current user's devices."""
        return await self._repository.list_for_user(
            current_user.id,
            include_revoked=include_revoked,
            include_deleted=include_deleted,
        )

    async def get_device(self, current_user: User, device_id: UUID) -> Device:
        """Return a device owned by the current user."""
        return await self._require_owned_device(current_user, device_id)

    async def update_device(self, current_user: User, device_id: UUID, request: UpdateDeviceRequest) -> Device:
        """Rename or update platform metadata for a current user's device."""
        device = await self._require_owned_device(current_user, device_id)
        if device.trust_status == "revoked":
            raise ResourceConflict("Revoked devices cannot be updated")
        if request.name is not None:
            device.name = request.name
        if request.platform is not None:
            device.platform = request.platform
        await self._repository.save(device)
        await self._db.commit()
        logger.info("Updated device %s for user %s", device.id, current_user.id)
        return device

    async def trust_device(self, current_user: User, device_id: UUID) -> Device:
        """Trust a pending device."""
        device = await self._require_owned_device(current_user, device_id, include_deleted=True)
        if device.trust_status == "revoked" or device.deleted_at is not None:
            raise ResourceConflict("Revoked devices must be registered again")
        if device.trust_status == "trusted":
            return device
        await self._repository.trust(device)
        await self._db.commit()
        logger.info("Trusted device %s for user %s", device.id, current_user.id)
        return device

    async def revoke_device(self, current_user: User, device_id: UUID) -> None:
        """Revoke and soft delete a device."""
        device = await self._require_owned_device(current_user, device_id)
        if device.trust_status != "revoked":
            await self._repository.revoke(device)
            await self._db.commit()
            logger.info("Revoked device %s for user %s", device.id, current_user.id)

    async def heartbeat(self, current_user: User, device_id: UUID) -> Device:
        """Update device last seen timestamp."""
        device = await self._require_owned_device(current_user, device_id)
        if device.trust_status == "revoked":
            raise ResourceConflict("Revoked devices cannot send heartbeats")
        await self._repository.heartbeat(device)
        await self._db.commit()
        logger.info("Heartbeat from device %s for user %s", device.id, current_user.id)
        return device

    async def _require_owned_device(self, current_user: User, device_id: UUID, include_deleted: bool = False) -> Device:
        """Load a non-deleted owned device or raise 404."""
        device = await self._repository.get_for_user(device_id, current_user.id, include_deleted=include_deleted)
        if device is None:
            raise ResourceNotFound("Device not found")
        return device
