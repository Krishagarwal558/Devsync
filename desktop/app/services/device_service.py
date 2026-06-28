"""Device setup service."""

from __future__ import annotations

import platform

from desktop.app.core.device_client import DeviceClient
from desktop.app.core.local_state import LocalStateStore


class DesktopDeviceService:
    """Registers or reuses a trusted cloud device."""

    def __init__(self, state: LocalStateStore, client: DeviceClient) -> None:
        self._state = state
        self._client = client

    async def ensure_device(self) -> dict[str, object]:
        """Return selected trusted device, registering one if needed."""
        existing_device_id = self._state.get_setting("device_id")
        devices = await self._client.list_devices()
        if existing_device_id:
            for device in devices:
                if str(device["id"]) == existing_device_id and device.get("trust_status") == "trusted":
                    return device
        name = f"{platform.node() or 'DevSync'} Desktop"
        device = await self._client.register_device(name)
        if device.get("trust_status") != "trusted":
            device = await self._client.trust_device(str(device["id"]))
        self._state.save_setting("device_id", str(device["id"]))
        self._state.save_setting("device_name", str(device["name"]))
        return device

