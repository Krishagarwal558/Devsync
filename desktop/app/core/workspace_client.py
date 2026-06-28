"""Workspace REST client."""

from __future__ import annotations

from desktop.app.core.auth_client import AuthorizedClient


class WorkspaceClient:
    """Client for workspace APIs."""

    def __init__(self, authorized: AuthorizedClient) -> None:
        self._authorized = authorized

    async def list_workspaces(self) -> list[dict[str, object]]:
        """List user's cloud workspaces."""
        async with self._authorized.client() as client:
            response = await client.get("/v1/workspaces")
            response.raise_for_status()
            return response.json()

