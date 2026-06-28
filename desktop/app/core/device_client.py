"""Device REST client."""

from __future__ import annotations

import platform

from desktop.app.core.auth_client import AuthorizedClient


class DeviceClient:
    """Client for device APIs."""

    def __init__(self, authorized: AuthorizedClient) -> None:
        self._authorized = authorized

    async def list_devices(self) -> list[dict[str, object]]:
        """List devices for current user."""
        async with self._authorized.client() as client:
            response = await client.get("/v1/devices")
            response.raise_for_status()
            return response.json()

    async def register_device(self, name: str) -> dict[str, object]:
        """Register this desktop device."""
        async with self._authorized.client() as client:
            response = await client.post(
                "/v1/devices",
                json={"name": name, "platform": platform.system().lower()},
            )
            response.raise_for_status()
            return response.json()

    async def trust_device(self, device_id: str) -> dict[str, object]:
        """Trust a device. MVP lets the signed-in user trust their own device."""
        async with self._authorized.client() as client:
            response = await client.post(f"/v1/devices/{device_id}/trust")
            response.raise_for_status()
            return response.json()

    async def heartbeat(self, device_id: str) -> dict[str, object]:
        """Send REST heartbeat."""
        async with self._authorized.client() as client:
            response = await client.post(f"/v1/devices/{device_id}/heartbeat")
            response.raise_for_status()
            return response.json()

