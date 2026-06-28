"""Password and token security services."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from passlib.context import CryptContext

from server.app.config.settings import Settings
from server.app.utils.errors import AuthenticationFailed


class PasswordHasher:
    """Password hashing and verification using passlib bcrypt."""

    def __init__(self, bcrypt_rounds: int) -> None:
        """Create a password hasher."""
        self._context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=bcrypt_rounds,
        )

    def hash_password(self, password: str) -> str:
        """Hash a plain password."""
        return self._context.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plain password against a stored hash."""
        return bool(self._context.verify(password, password_hash))


class TokenService:
    """Creates JWT access tokens and opaque refresh tokens."""

    def __init__(self, settings: Settings) -> None:
        """Create a token service."""
        self._settings = settings

    @property
    def access_token_ttl_seconds(self) -> int:
        """Return access token lifetime in seconds."""
        return self._settings.access_token_minutes * 60

    def create_access_token(self, user_id: UUID, session_id: UUID) -> str:
        """Create a signed short-lived access token."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self._settings.access_token_minutes)
        payload = {
            "sub": str(user_id),
            "sid": str(session_id),
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(
            payload,
            self._settings.jwt_secret_key.get_secret_value(),
            algorithm=self._settings.jwt_algorithm,
        )

    def decode_access_token(self, token: str) -> dict[str, str]:
        """Decode and validate an access token."""
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key.get_secret_value(),
                algorithms=[self._settings.jwt_algorithm],
                options={"require": ["sub", "sid", "exp", "iat", "type"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationFailed("Invalid or expired access token") from exc
        if payload.get("type") != "access":
            raise AuthenticationFailed("Invalid access token")
        return {"sub": str(payload["sub"]), "sid": str(payload["sid"])}

    def create_refresh_token(self) -> str:
        """Create a cryptographically random refresh token."""
        return secrets.token_urlsafe(48)

    def hash_refresh_token(self, token: str) -> str:
        """Hash a refresh token for safe database storage."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def refresh_expires_at(self) -> datetime:
        """Return the expiry timestamp for a newly issued refresh token."""
        return datetime.now(timezone.utc) + timedelta(days=self._settings.refresh_token_days)

