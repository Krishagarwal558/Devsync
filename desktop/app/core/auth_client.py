"""Authentication REST client."""

from __future__ import annotations

import httpx


class AuthClient:
    """Client for DevSync auth APIs."""

    def __init__(self, server_url: str) -> None:
        self._server_url = server_url.rstrip("/")

    async def login(self, email: str, password: str) -> dict[str, object]:
        """Login and return auth payload."""
        async with httpx.AsyncClient(base_url=self._server_url, timeout=20) as client:
            response = await client.post("/v1/auth/login", json={"email": email, "password": password})
            response.raise_for_status()
            return response.json()


class AuthorizedClient:
    """Small helper around authenticated REST requests."""

    def __init__(self, server_url: str, access_token: str) -> None:
        self._server_url = server_url.rstrip("/")
        self._access_token = access_token

    def client(self) -> httpx.AsyncClient:
        """Create an authenticated AsyncClient."""
        return httpx.AsyncClient(
            base_url=self._server_url,
            timeout=60,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

