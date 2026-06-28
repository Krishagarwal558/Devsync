"""Device repository."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.devices.models import Device


class DeviceRepository:
    """Database access for devices."""

    def __init__(self, session: AsyncSession) -> None:
        """Create repository."""
        self._session = session

    async def create_device(
        self,
        user_id: UUID,
        name: str,
        platform: str,
        public_key: str | None,
    ) -> Device:
        """Persist a new pending device."""
        device = Device(
            user_id=user_id,
            name=name,
            platform=platform,
            public_key=public_key,
            trust_status="pending",
        )
        self._session.add(device)
        await self._session.flush()
        await self._session.refresh(device)
        return device

    async def list_for_user(self, user_id: UUID, include_revoked: bool = False, include_deleted: bool = False) -> list[Device]:
        """Return devices owned by a user."""
        statement: Select[tuple[Device]] = (
            select(Device)
            .where(Device.user_id == user_id)
            .order_by(Device.updated_at.desc())
        )
        if not include_revoked:
            statement = statement.where(Device.trust_status != "revoked")
        if not include_deleted:
            statement = statement.where(Device.deleted_at.is_(None))
        return list((await self._session.scalars(statement)).all())

    async def get_for_user(self, device_id: UUID, user_id: UUID, include_deleted: bool = False) -> Device | None:
        """Return a device owned by a user."""
        statement: Select[tuple[Device]] = select(Device).where(Device.id == device_id, Device.user_id == user_id)
        if not include_deleted:
            statement = statement.where(Device.deleted_at.is_(None))
        return await self._session.scalar(statement)

    async def save(self, device: Device) -> Device:
        """Flush device changes."""
        await self._session.flush()
        await self._session.refresh(device)
        return device

    async def trust(self, device: Device) -> Device:
        """Mark a pending device as trusted."""
        device.trust_status = "trusted"
        return await self.save(device)

    async def revoke(self, device: Device) -> Device:
        """Revoke and soft delete a device."""
        now = datetime.now(timezone.utc)
        device.trust_status = "revoked"
        device.deleted_at = now
        return await self.save(device)

    async def heartbeat(self, device: Device) -> Device:
        """Update device last seen timestamp."""
        device.last_seen_at = datetime.now(timezone.utc)
        return await self.save(device)

