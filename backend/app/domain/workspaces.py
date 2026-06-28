"""Workspace and team domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from .identity import now_utc


class WorkspaceStatus(StrEnum):
    """Lifecycle states for a workspace."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class WorkspaceRole(StrEnum):
    """Built-in workspace roles."""

    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


@dataclass(frozen=True)
class Workspace:
    """A synchronized development workspace."""

    id: UUID
    owner_id: UUID
    name: str
    status: WorkspaceStatus
    created_at: datetime
    archived_at: datetime | None

    @classmethod
    def create(cls, owner_id: UUID, name: str) -> "Workspace":
        """Create a new active workspace."""
        return cls(
            id=uuid4(),
            owner_id=owner_id,
            name=name.strip(),
            status=WorkspaceStatus.ACTIVE,
            created_at=now_utc(),
            archived_at=None,
        )

    def archive(self) -> "Workspace":
        """Return an archived copy of this workspace."""
        return Workspace(
            id=self.id,
            owner_id=self.owner_id,
            name=self.name,
            status=WorkspaceStatus.ARCHIVED,
            created_at=self.created_at,
            archived_at=now_utc(),
        )


@dataclass(frozen=True)
class WorkspaceMember:
    """A user's membership in a workspace."""

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    joined_at: datetime


class PermissionPolicy:
    """Authorizes workspace actions from built-in roles."""

    _permissions: dict[WorkspaceRole, set[str]] = {
        WorkspaceRole.OWNER: {
            "workspace:read",
            "workspace:write",
            "workspace:delete",
            "members:manage",
            "devices:manage",
            "sync:write",
        },
        WorkspaceRole.ADMIN: {
            "workspace:read",
            "workspace:write",
            "members:manage",
            "devices:manage",
            "sync:write",
        },
        WorkspaceRole.DEVELOPER: {
            "workspace:read",
            "workspace:write",
            "sync:write",
        },
        WorkspaceRole.VIEWER: {
            "workspace:read",
        },
    }

    def allows(self, role: WorkspaceRole, action: str) -> bool:
        """Return whether a role permits an action."""
        return action in self._permissions[role]

