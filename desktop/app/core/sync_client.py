"""Sync event REST client."""

from __future__ import annotations

from desktop.app.core.auth_client import AuthorizedClient


class SyncClient:
    """Client for sync protocol REST APIs."""

    def __init__(self, authorized: AuthorizedClient) -> None:
        self._authorized = authorized

    async def ack(self, workspace_id: str, device_id: str, sequence: int) -> dict[str, object]:
        """Acknowledge sync events up to sequence."""
        async with self._authorized.client() as client:
            response = await client.post(
                f"/v1/workspaces/{workspace_id}/sync/ack",
                json={"device_id": device_id, "up_to_sequence": sequence},
            )
            response.raise_for_status()
            return response.json()

