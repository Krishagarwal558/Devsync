"""Workspace use cases."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.app.application.repositories import UserRepository, WorkspaceRepository
from backend.app.domain.identity import now_utc
from backend.app.domain.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from shared.devsync_shared.errors import NotFoundError


@dataclass(frozen=True)
class CreateWorkspaceCommand:
    """Input data for workspace creation."""

    owner_id: UUID
    name: str


class CreateWorkspaceUseCase:
    """Creates a workspace and owner membership."""

    def __init__(self, users: UserRepository, workspaces: WorkspaceRepository) -> None:
        """Create the use case."""
        self._users = users
        self._workspaces = workspaces

    def execute(self, command: CreateWorkspaceCommand) -> Workspace:
        """Create a workspace owned by a user."""
        if self._users.get(command.owner_id) is None:
            raise NotFoundError("Owner not found")
        workspace = Workspace.create(command.owner_id, command.name)
        self._workspaces.add(workspace)
        self._workspaces.add_member(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=command.owner_id,
                role=WorkspaceRole.OWNER,
                joined_at=now_utc(),
            )
        )
        return workspace


class ListWorkspacesUseCase:
    """Lists workspaces visible to a user."""

    def __init__(self, workspaces: WorkspaceRepository) -> None:
        """Create the use case."""
        self._workspaces = workspaces

    def execute(self, user_id: UUID) -> list[Workspace]:
        """Return workspaces visible to a user."""
        return self._workspaces.list_for_user(user_id)

