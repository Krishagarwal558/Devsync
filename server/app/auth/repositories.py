"""Authentication repositories."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.auth.models import Session, User


class AuthRepository:
    """Database access for users and sessions."""

    def __init__(self, session: AsyncSession) -> None:
        """Create repository."""
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        """Return an active user by normalized email."""
        statement: Select[tuple[User]] = select(User).where(
            func.lower(User.email) == email.lower(),
            User.deleted_at.is_(None),
        )
        return await self._session.scalar(statement)

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Return an active user by id."""
        statement: Select[tuple[User]] = select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
        return await self._session.scalar(statement)

    async def create_user(self, email: str, display_name: str, password_hash: str) -> User:
        """Persist a new user."""
        user = User(email=email.lower(), display_name=display_name, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def create_session(
        self,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
    ) -> Session:
        """Persist a refresh session."""
        session = Session(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
        )
        self._session.add(session)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    async def get_active_session_by_refresh_hash(self, refresh_token_hash: str) -> Session | None:
        """Return an active session matching a refresh token hash."""
        statement: Select[tuple[Session]] = select(Session).where(
            Session.refresh_token_hash == refresh_token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(timezone.utc),
        )
        return await self._session.scalar(statement)

    async def get_active_session_by_id(self, session_id: UUID) -> Session | None:
        """Return an active session by id."""
        statement: Select[tuple[Session]] = select(Session).where(
            Session.id == session_id,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(timezone.utc),
        )
        return await self._session.scalar(statement)

    async def rotate_session(
        self,
        session: Session,
        refresh_token_hash: str,
        expires_at: datetime,
    ) -> Session:
        """Rotate a session's refresh token hash and expiry."""
        session.refresh_token_hash = refresh_token_hash
        session.expires_at = expires_at
        await self._session.flush()
        await self._session.refresh(session)
        return session

    async def revoke_session(self, session: Session) -> None:
        """Revoke a session."""
        session.revoked_at = datetime.now(timezone.utc)
        await self._session.flush()

