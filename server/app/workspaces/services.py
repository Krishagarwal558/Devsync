"""Workspace service workflows."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.auth.models import User
from server.app.utils.errors import PermissionDenied, ResourceConflict, ResourceNotFound
from server.app.workspaces.models import Workspace, WorkspaceMember
from server.app.workspaces.repositories import WorkspaceRepository
from server.app.workspaces.schemas import CreateWorkspaceRequest, UpdateWorkspaceRequest
from server.app.workspaces.slug import slugify

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Workspace management use cases."""

    def __init__(self, db: AsyncSession, repository: WorkspaceRepository) -> None:
        """Create workspace service."""
        self._db = db
        self._repository = repository

    async def create_workspace(self, current_user: User, request: CreateWorkspaceRequest) -> tuple[Workspace, WorkspaceMember]:
        """Create a workspace and owner membership."""
        slug = await self._unique_slug(current_user.id, slugify(request.name))
        try:
            workspace = await self._repository.create_workspace(
                owner_id=current_user.id,
                name=request.name,
                slug=slug,
                settings=request.settings,
            )
            membership = await self._repository.create_owner_membership(workspace.id, current_user.id)
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise ResourceConflict("A workspace with this name already exists") from exc

        logger.info("Created workspace %s for user %s", workspace.id, current_user.id)
        return workspace, membership

    async def list_workspaces(
        self,
        current_user: User,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[Workspace]:
        """List workspaces visible to the current user."""
        return await self._repository.list_for_user(
            current_user.id,
            include_archived=include_archived,
            include_deleted=include_deleted,
        )

    async def get_workspace(self, current_user: User, workspace_id: UUID) -> tuple[Workspace, WorkspaceMember]:
        """Return a workspace visible to current user."""
        return await self._require_visible_workspace(current_user, workspace_id)

    async def update_workspace(
        self,
        current_user: User,
        workspace_id: UUID,
        request: UpdateWorkspaceRequest,
    ) -> tuple[Workspace, WorkspaceMember]:
        """Rename a workspace or update workspace settings."""
        workspace, membership = await self._require_visible_workspace(current_user, workspace_id)
        self._require_owner(membership)

        if request.name is not None and request.name != workspace.name:
            workspace.name = request.name
            workspace.slug = await self._unique_slug(
                current_user.id,
                slugify(request.name),
                exclude_workspace_id=workspace.id,
            )
        if request.settings is not None:
            workspace.settings = request.settings

        try:
            await self._repository.save(workspace)
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise ResourceConflict("A workspace with this name already exists") from exc

        logger.info("Updated workspace %s by user %s", workspace.id, current_user.id)
        return workspace, membership

    async def archive_workspace(self, current_user: User, workspace_id: UUID) -> tuple[Workspace, WorkspaceMember]:
        """Archive a workspace."""
        workspace, membership = await self._require_visible_workspace(current_user, workspace_id)
        self._require_owner(membership)
        if workspace.status == "archived":
            return workspace, membership
        await self._repository.archive(workspace)
        await self._db.commit()
        logger.info("Archived workspace %s by user %s", workspace.id, current_user.id)
        return workspace, membership

    async def delete_workspace(self, current_user: User, workspace_id: UUID) -> None:
        """Soft delete a workspace."""
        workspace, membership = await self._require_visible_workspace(current_user, workspace_id)
        self._require_owner(membership)
        await self._repository.soft_delete(workspace, membership)
        await self._db.commit()
        logger.info("Soft deleted workspace %s by user %s", workspace.id, current_user.id)

    async def _require_visible_workspace(self, current_user: User, workspace_id: UUID) -> tuple[Workspace, WorkspaceMember]:
        """Load a visible workspace or raise 404."""
        result = await self._repository.get_visible_workspace(workspace_id, current_user.id)
        if result is None:
            raise ResourceNotFound("Workspace not found")
        return result

    def _require_owner(self, membership: WorkspaceMember) -> None:
        """Require owner membership for mutations."""
        if membership.role != "owner":
            raise PermissionDenied("Only the workspace owner can perform this action")

    async def _unique_slug(self, owner_id: UUID, base_slug: str, exclude_workspace_id: UUID | None = None) -> str:
        """Generate a unique active slug for an owner."""
        candidate = base_slug
        suffix = 2
        while await self._repository.active_slug_exists_for_owner(
            owner_id,
            candidate,
            exclude_workspace_id=exclude_workspace_id,
        ):
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        return candidate

