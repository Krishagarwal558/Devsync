"""JWT-compatible HMAC token service without external dependencies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from shared.devsync_shared.errors import AuthenticationError


def _b64encode(raw: bytes) -> str:
    """Encode bytes as unpadded URL-safe base64."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    """Decode unpadded URL-safe base64."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


@dataclass(frozen=True)
class TokenPair:
    """Access and refresh tokens issued after authentication."""

    access_token: str
    refresh_token: str
    expires_at: datetime


class TokenService:
    """Creates and verifies signed JSON tokens."""

    def __init__(self, secret: str, issuer: str, access_minutes: int = 15, refresh_days: int = 30) -> None:
        """Create a token service."""
        self._secret = secret.encode("utf-8")
        self._issuer = issuer
        self._access_minutes = access_minutes
        self._refresh_days = refresh_days

    def issue_pair(self, user_id: UUID, device_id: UUID | None = None) -> TokenPair:
        """Issue an access/refresh token pair."""
        access_expires = datetime.now(timezone.utc) + timedelta(minutes=self._access_minutes)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=self._refresh_days)
        access = self._sign(
            {
                "sub": str(user_id),
                "device_id": str(device_id) if device_id else None,
                "iss": self._issuer,
                "type": "access",
                "exp": int(access_expires.timestamp()),
            }
        )
        refresh = self._sign(
            {
                "sub": str(user_id),
                "device_id": str(device_id) if device_id else None,
                "iss": self._issuer,
                "type": "refresh",
                "exp": int(refresh_expires.timestamp()),
            }
        )
        return TokenPair(access, refresh, access_expires)

    def verify(self, token: str, expected_type: str) -> dict[str, Any]:
        """Verify a token signature, expiry, issuer, and type."""
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationError("Invalid token format")
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        expected_signature = self._signature(signing_input)
        actual_signature = _b64decode(parts[2])
        if not hmac.compare_digest(actual_signature, expected_signature):
            raise AuthenticationError("Invalid token signature")
        payload = json.loads(_b64decode(parts[1]))
        if payload.get("iss") != self._issuer:
            raise AuthenticationError("Invalid token issuer")
        if payload.get("type") != expected_type:
            raise AuthenticationError("Invalid token type")
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise AuthenticationError("Token expired")
        return payload

    def _sign(self, payload: dict[str, Any]) -> str:
        """Sign a JSON payload as a compact token."""
        header = {"alg": "HS256", "typ": "JWT"}
        header_part = _b64encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        payload_part = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        return f"{header_part}.{payload_part}.{_b64encode(self._signature(signing_input))}"

    def _signature(self, signing_input: bytes) -> bytes:
        """Return the HMAC-SHA256 signature for token input."""
        return hmac.new(self._secret, signing_input, hashlib.sha256).digest()

