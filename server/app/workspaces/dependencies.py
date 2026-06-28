"""Workspace dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.database.session import get_db_session
from server.app.workspaces.repositories import WorkspaceRepository
from server.app.workspaces.services import WorkspaceService


def get_workspace_repository(db: Annotated[AsyncSession, Depends(get_db_session)]) -> WorkspaceRepository:
    """Create workspace repository."""
    return WorkspaceRepository(db)


def get_workspace_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> WorkspaceService:
    """Create workspace service."""
    return WorkspaceService(db, repository)

