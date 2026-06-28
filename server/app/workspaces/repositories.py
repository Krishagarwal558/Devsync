"""Workspace repository."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from server.app.workspaces.models import Workspace, WorkspaceMember


class WorkspaceRepository:
    """Database access for workspaces and owner membership."""

    def __init__(self, session: AsyncSession) -> None:
        """Create repository."""
        self._session = session

    async def create_workspace(
        self,
        owner_id: UUID,
        name: str,
        slug: str,
        settings: dict[str, object],
    ) -> Workspace:
        """Persist a workspace."""
        workspace = Workspace(owner_id=owner_id, name=name, slug=slug, settings=settings)
        self._session.add(workspace)
        await self._session.flush()
        await self._session.refresh(workspace)
        return workspace

    async def create_owner_membership(self, workspace_id: UUID, owner_id: UUID) -> WorkspaceMember:
        """Persist owner membership for a workspace."""
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=owner_id,
            role="owner",
            status="active",
        )
        self._session.add(membership)
        await self._session.flush()
        await self._session.refresh(membership)
        return membership

    async def list_for_user(
        self,
        user_id: UUID,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[Workspace]:
        """Return workspaces where the user is an active member."""
        statement: Select[tuple[Workspace]] = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == "active",
                WorkspaceMember.deleted_at.is_(None),
            )
            .order_by(Workspace.updated_at.desc())
        )
        if not include_archived:
            statement = statement.where(Workspace.status != "archived")
        if not include_deleted:
            statement = statement.where(Workspace.deleted_at.is_(None), Workspace.status != "deleted")
        return list((await self._session.scalars(statement)).all())

    async def get_visible_workspace(self, workspace_id: UUID, user_id: UUID) -> tuple[Workspace, WorkspaceMember] | None:
        """Return a workspace and active member row visible to a user."""
        statement = (
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                Workspace.id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == "active",
                WorkspaceMember.deleted_at.is_(None),
                Workspace.deleted_at.is_(None),
                Workspace.status != "deleted",
            )
            .options(selectinload(Workspace.members))
        )
        row = (await self._session.execute(statement)).first()
        if row is None:
            return None
        return row[0], row[1]

    async def active_slug_exists_for_owner(self, owner_id: UUID, slug: str, exclude_workspace_id: UUID | None = None) -> bool:
        """Return whether an active non-deleted workspace slug already exists for an owner."""
        statement = select(Workspace.id).where(
            Workspace.owner_id == owner_id,
            Workspace.slug == slug,
            Workspace.deleted_at.is_(None),
            Workspace.status != "deleted",
        )
        if exclude_workspace_id is not None:
            statement = statement.where(Workspace.id != exclude_workspace_id)
        return (await self._session.scalar(statement)) is not None

    async def save(self, workspace: Workspace) -> Workspace:
        """Flush workspace changes."""
        await self._session.flush()
        await self._session.refresh(workspace)
        return workspace

    async def archive(self, workspace: Workspace) -> Workspace:
        """Archive a workspace."""
        workspace.status = "archived"
        workspace.archived_at = datetime.now(timezone.utc)
        return await self.save(workspace)

    async def soft_delete(self, workspace: Workspace, membership: WorkspaceMember) -> Workspace:
        """Soft delete a workspace and remove the active owner membership."""
        now = datetime.now(timezone.utc)
        workspace.status = "deleted"
        workspace.deleted_at = now
        membership.status = "removed"
        membership.deleted_at = now
        await self._session.flush()
        await self._session.refresh(workspace)
        return workspace

