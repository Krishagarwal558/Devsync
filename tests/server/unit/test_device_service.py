from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from server.app.auth.models import User
from server.app.devices.models import Device
from server.app.devices.schemas import RegisterDeviceRequest, UpdateDeviceRequest
from server.app.devices.services import DeviceService
from server.app.utils.errors import ResourceConflict, ResourceNotFound


class UnitOfWorkStub:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class DeviceRepositoryStub:
    def __init__(self) -> None:
        self.devices: dict[uuid.UUID, Device] = {}

    async def create_device(self, user_id: uuid.UUID, name: str, platform: str, public_key: str | None) -> Device:
        now = datetime.now(timezone.utc)
        device = Device(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            platform=platform,
            public_key=public_key,
            trust_status="pending",
            last_seen_at=None,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        self.devices[device.id] = device
        return device

    async def list_for_user(self, user_id: uuid.UUID, include_revoked: bool = False, include_deleted: bool = False) -> list[Device]:
        devices = [device for device in self.devices.values() if device.user_id == user_id]
        if not include_revoked:
            devices = [device for device in devices if device.trust_status != "revoked"]
        if not include_deleted:
            devices = [device for device in devices if device.deleted_at is None]
        return devices

    async def get_for_user(self, device_id: uuid.UUID, user_id: uuid.UUID, include_deleted: bool = False) -> Device | None:
        device = self.devices.get(device_id)
        if device is None or device.user_id != user_id:
            return None
        if device.deleted_at is not None and not include_deleted:
            return None
        return device

    async def save(self, device: Device) -> Device:
        self.devices[device.id] = device
        return device

    async def trust(self, device: Device) -> Device:
        device.trust_status = "trusted"
        return await self.save(device)

    async def revoke(self, device: Device) -> Device:
        device.trust_status = "revoked"
        device.deleted_at = datetime.now(timezone.utc)
        return await self.save(device)

    async def heartbeat(self, device: Device) -> Device:
        device.last_seen_at = datetime.now(timezone.utc)
        return await self.save(device)


def make_user(email: str = "owner@example.com") -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        display_name="Owner",
        password_hash="hash",
        status="active",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.anyio
async def test_register_device_creates_pending_owned_device() -> None:
    db = UnitOfWorkStub()
    repo = DeviceRepositoryStub()
    service = DeviceService(db, repo)  # type: ignore[arg-type]
    user = make_user()

    device = await service.register_device(
        user,
        RegisterDeviceRequest(name="Shrey Laptop", platform="windows", public_key="public-key"),
    )

    assert device.user_id == user.id
    assert device.trust_status == "pending"
    assert device.public_key == "public-key"
    assert db.committed


@pytest.mark.anyio
async def test_trust_device_marks_pending_device_trusted() -> None:
    db = UnitOfWorkStub()
    repo = DeviceRepositoryStub()
    service = DeviceService(db, repo)  # type: ignore[arg-type]
    user = make_user()
    device = await service.register_device(user, RegisterDeviceRequest(name="Laptop", platform="windows"))

    trusted = await service.trust_device(user, device.id)

    assert trusted.trust_status == "trusted"


@pytest.mark.anyio
async def test_update_and_heartbeat_require_owned_active_device() -> None:
    db = UnitOfWorkStub()
    repo = DeviceRepositoryStub()
    service = DeviceService(db, repo)  # type: ignore[arg-type]
    user = make_user()
    other_user = make_user("other@example.com")
    device = await service.register_device(user, RegisterDeviceRequest(name="Laptop", platform="windows"))

    updated = await service.update_device(user, device.id, UpdateDeviceRequest(name="Desktop", platform="linux"))
    heartbeat = await service.heartbeat(user, device.id)

    assert updated.name == "Desktop"
    assert updated.platform == "linux"
    assert heartbeat.last_seen_at is not None
    with pytest.raises(ResourceNotFound):
        await service.get_device(other_user, device.id)


@pytest.mark.anyio
async def test_revoked_device_cannot_be_trusted_again() -> None:
    db = UnitOfWorkStub()
    repo = DeviceRepositoryStub()
    service = DeviceService(db, repo)  # type: ignore[arg-type]
    user = make_user()
    device = await service.register_device(user, RegisterDeviceRequest(name="Laptop", platform="windows"))

    await service.revoke_device(user, device.id)

    assert device.trust_status == "revoked"
    assert device.deleted_at is not None
    with pytest.raises(ResourceConflict):
        await service.trust_device(user, device.id)

