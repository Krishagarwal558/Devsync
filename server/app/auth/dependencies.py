"""Authentication dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.auth.models import User
from server.app.auth.repositories import AuthRepository
from server.app.auth.security import PasswordHasher, TokenService
from server.app.auth.services import AuthService
from server.app.config.settings import Settings, get_settings
from server.app.database.session import get_db_session
from server.app.utils.errors import AuthenticationFailed

bearer_scheme = HTTPBearer(auto_error=False)


def get_password_hasher(settings: Annotated[Settings, Depends(get_settings)]) -> PasswordHasher:
    """Create a password hasher from settings."""
    return PasswordHasher(settings.bcrypt_rounds)


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> TokenService:
    """Create a token service from settings."""
    return TokenService(settings)


def get_auth_repository(db: Annotated[AsyncSession, Depends(get_db_session)]) -> AuthRepository:
    """Create auth repository."""
    return AuthRepository(db)


def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    repository: Annotated[AuthRepository, Depends(get_auth_repository)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthService:
    """Create auth service."""
    return AuthService(db, repository, password_hasher, token_service)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Return the authenticated current user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationFailed("Authentication is required")
    return await auth_service.get_current_user(credentials.credentials)

