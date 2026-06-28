"""Application dependency container."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.infrastructure.memory_repositories import (
    InMemoryDeviceRepository,
    InMemorySyncOperationRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from backend.app.security.passwords import PasswordHasher
from backend.app.security.tokens import TokenService
from backend.app.settings.config import BackendSettings


@dataclass(frozen=True)
class BackendContainer:
    """Holds backend service dependencies."""

    settings: BackendSettings
    users: InMemoryUserRepository
    devices: InMemoryDeviceRepository
    workspaces: InMemoryWorkspaceRepository
    sync_operations: InMemorySyncOperationRepository
    password_hasher: PasswordHasher
    token_service: TokenService


def build_container(settings: BackendSettings | None = None) -> BackendContainer:
    """Build a backend dependency container."""
    loaded_settings = settings or BackendSettings.from_environment()
    return BackendContainer(
        settings=loaded_settings,
        users=InMemoryUserRepository(),
        devices=InMemoryDeviceRepository(),
        workspaces=InMemoryWorkspaceRepository(),
        sync_operations=InMemorySyncOperationRepository(),
        password_hasher=PasswordHasher(),
        token_service=TokenService(
            secret=loaded_settings.token_secret,
            issuer=loaded_settings.token_issuer,
        ),
    )

