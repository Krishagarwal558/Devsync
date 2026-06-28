"""Authentication service workflows."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.auth.models import User
from server.app.auth.repositories import AuthRepository
from server.app.auth.schemas import AuthResponse, LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest
from server.app.auth.security import PasswordHasher, TokenService
from server.app.utils.errors import AuthenticationFailed, ResourceConflict

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication use cases."""

    def __init__(
        self,
        db: AsyncSession,
        repository: AuthRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        """Create the service."""
        self._db = db
        self._repository = repository
        self._password_hasher = password_hasher
        self._token_service = token_service

    async def register(self, request: RegisterRequest) -> AuthResponse:
        """Register a user and create an authenticated session."""
        existing_user = await self._repository.get_user_by_email(str(request.email))
        if existing_user is not None:
            raise ResourceConflict("An account with this email already exists")

        password_hash = self._password_hasher.hash_password(request.password)
        refresh_token = self._token_service.create_refresh_token()
        refresh_hash = self._token_service.hash_refresh_token(refresh_token)

        try:
            user = await self._repository.create_user(
                email=str(request.email).lower(),
                display_name=request.display_name,
                password_hash=password_hash,
            )
            session = await self._repository.create_session(
                user_id=user.id,
                refresh_token_hash=refresh_hash,
                expires_at=self._token_service.refresh_expires_at(),
            )
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise ResourceConflict("An account with this email already exists") from exc

        logger.info("Registered user %s", user.id)
        return self._auth_response(user, session.id, refresh_token)

    async def login(self, request: LoginRequest) -> AuthResponse:
        """Authenticate credentials and create a session."""
        user = await self._repository.get_user_by_email(str(request.email))
        if user is None or not self._password_hasher.verify_password(request.password, user.password_hash):
            raise AuthenticationFailed("Email or password is incorrect")

        refresh_token = self._token_service.create_refresh_token()
        session = await self._repository.create_session(
            user_id=user.id,
            refresh_token_hash=self._token_service.hash_refresh_token(refresh_token),
            expires_at=self._token_service.refresh_expires_at(),
        )
        await self._db.commit()
        logger.info("User %s logged in with session %s", user.id, session.id)
        return self._auth_response(user, session.id, refresh_token)

    async def refresh(self, request: RefreshRequest) -> AuthResponse:
        """Rotate a refresh token and issue a new access token."""
        old_hash = self._token_service.hash_refresh_token(request.refresh_token)
        session = await self._repository.get_active_session_by_refresh_hash(old_hash)
        if session is None:
            raise AuthenticationFailed("Refresh token is invalid or expired")

        new_refresh_token = self._token_service.create_refresh_token()
        await self._repository.rotate_session(
            session=session,
            refresh_token_hash=self._token_service.hash_refresh_token(new_refresh_token),
            expires_at=self._token_service.refresh_expires_at(),
        )
        await self._db.commit()
        logger.info("Rotated refresh token for session %s", session.id)
        return self._auth_response(session.user, session.id, new_refresh_token)

    async def logout(self, request: LogoutRequest) -> None:
        """Revoke a refresh token session."""
        refresh_hash = self._token_service.hash_refresh_token(request.refresh_token)
        session = await self._repository.get_active_session_by_refresh_hash(refresh_hash)
        if session is None:
            return
        await self._repository.revoke_session(session)
        await self._db.commit()
        logger.info("Revoked session %s", session.id)

    async def get_current_user(self, access_token: str) -> User:
        """Return the active user represented by an access token."""
        token_payload = self._token_service.decode_access_token(access_token)
        user_id = UUID(token_payload["sub"])
        session_id = UUID(token_payload["sid"])

        session = await self._repository.get_active_session_by_id(session_id)
        if session is None or session.user_id != user_id:
            raise AuthenticationFailed("Session is no longer active")

        user = await self._repository.get_user_by_id(user_id)
        if user is None or user.status != "active":
            raise AuthenticationFailed("User is no longer active")
        return user

    def _auth_response(self, user: User, session_id: UUID, refresh_token: str) -> AuthResponse:
        """Build an auth response with access and refresh tokens."""
        return AuthResponse(
            access_token=self._token_service.create_access_token(user.id, session_id),
            refresh_token=refresh_token,
            expires_in=self._token_service.access_token_ttl_seconds,
            user=user,
        )

