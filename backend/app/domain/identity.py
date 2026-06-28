"""Identity, session, and device domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


def now_utc() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class DeviceTrustStatus(StrEnum):
    """Trust states for a registered device."""

    PENDING = "pending"
    TRUSTED = "trusted"
    REVOKED = "revoked"


@dataclass(frozen=True)
class User:
    """A DevSync account owner or workspace member."""

    id: UUID
    email: str
    display_name: str
    password_hash: str
    created_at: datetime

    @classmethod
    def create(cls, email: str, display_name: str, password_hash: str) -> "User":
        """Create a new user entity."""
        return cls(
            id=uuid4(),
            email=email.lower().strip(),
            display_name=display_name.strip(),
            password_hash=password_hash,
            created_at=now_utc(),
        )


@dataclass(frozen=True)
class Session:
    """A refresh-token session bound to a user and optional device."""

    id: UUID
    user_id: UUID
    refresh_token_hash: str
    expires_at: datetime
    device_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class Device:
    """A physical or virtual machine registered to a user."""

    id: UUID
    user_id: UUID
    name: str
    public_key: str
    trust_status: DeviceTrustStatus
    created_at: datetime
    last_seen_at: datetime | None

    @classmethod
    def register(cls, user_id: UUID, name: str, public_key: str) -> "Device":
        """Create a pending device registration."""
        return cls(
            id=uuid4(),
            user_id=user_id,
            name=name.strip(),
            public_key=public_key.strip(),
            trust_status=DeviceTrustStatus.PENDING,
            created_at=now_utc(),
            last_seen_at=None,
        )

    def trust(self) -> "Device":
        """Return a trusted copy of this device."""
        return Device(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            public_key=self.public_key,
            trust_status=DeviceTrustStatus.TRUSTED,
            created_at=self.created_at,
            last_seen_at=self.last_seen_at,
        )

    def revoke(self) -> "Device":
        """Return a revoked copy of this device."""
        return Device(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            public_key=self.public_key,
            trust_status=DeviceTrustStatus.REVOKED,
            created_at=self.created_at,
            last_seen_at=self.last_seen_at,
        )

