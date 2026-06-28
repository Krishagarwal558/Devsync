"""Device API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from server.app.auth.dependencies import get_current_user
from server.app.auth.models import User
from server.app.devices.dependencies import get_device_service
from server.app.devices.schemas import DeviceResponse, RegisterDeviceRequest, UpdateDeviceRequest
from server.app.devices.services import DeviceService

router = APIRouter(prefix="/v1/devices", tags=["devices"])


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    request: RegisterDeviceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    device_service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceResponse:
    """Register a device for the current user."""
    device = await device_service.register_device(current_user, request)
    return DeviceResponse.model_validate(device)


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    current_user: Annotated[User, Depends(get_current_user)],
    device_service: Annotated[DeviceService, Depends(get_device_service)],
    include_revoked: Annotated[bool, Query()] = False,
    include_deleted: Annotated[bool, Query()] = False,
) -> list[DeviceResponse]:
    """List current user's devices."""
    devices = await device_service.list_devices(
        current_user,
        include_revoked=include_revoked,
        include_deleted=include_deleted,
    )
    return [DeviceResponse.model_validate(device) for device in devices]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    device_service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceResponse:
    """Get device details."""
    device = await device_service.get_device(current_user, device_id)
    return DeviceResponse.model_validate(device)


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    request: UpdateDeviceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    device_service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceResponse:
    """Rename or update a device."""
    device = await device_service.update_device(current_user, device_id, request)
    return DeviceResponse.model_validate(device)


@router.post("/{device_id}/trust", response_model=DeviceResponse)
async def trust_device(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    device_service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceResponse:
    """Trust a pending device."""
    device = await device_service.trust_device(current_user, device_id)
    return DeviceResponse.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    device_service: Annotated[DeviceService, Depends(get_device_service)],
) -> None:
    """Revoke and remove a device from normal results."""
    await device_service.revoke_device(current_user, device_id)


@router.post("/{device_id}/heartbeat", response_model=DeviceResponse)
async def device_heartbeat(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    device_service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceResponse:
    """Update device last seen timestamp."""
    device = await device_service.heartbeat(current_user, device_id)
    return DeviceResponse.model_validate(device)

