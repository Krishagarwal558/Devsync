from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from server.app.auth.models import User
from server.app.utils.errors import PermissionDenied, ResourceNotFound
from server.app.workspaces.models import Workspace, WorkspaceMember
from server.app.workspaces.schemas import CreateWorkspaceRequest, UpdateWorkspaceRequest
from server.app.workspaces.services import WorkspaceService
from server.app.workspaces.slug import slugify


class UnitOfWorkStub:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class WorkspaceRepositoryStub:
    def __init__(self) -> None:
        self.workspace: Workspace | None = None
        self.membership: WorkspaceMember | None = None
        self.existing_slugs: set[str] = set()

    async def active_slug_exists_for_owner(self, owner_id: uuid.UUID, slug: str, exclude_workspace_id: uuid.UUID | None = None) -> bool:
        return slug in self.existing_slugs

    async def create_workspace(self, owner_id: uuid.UUID, name: str, slug: str, settings: dict[str, object]) -> Workspace:
        self.workspace = Workspace(
            id=uuid.uuid4(),
            owner_id=owner_id,
            name=name,
            slug=slug,
            status="active",
            settings=settings,
            archived_at=None,
            deleted_at=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return self.workspace

    async def create_owner_membership(self, workspace_id: uuid.UUID, owner_id: uuid.UUID) -> WorkspaceMember:
        self.membership = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=owner_id,
            role="owner",
            status="active",
            deleted_at=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return self.membership

    async def list_for_user(self, user_id: uuid.UUID, include_archived: bool = False, include_deleted: bool = False) -> list[Workspace]:
        return [self.workspace] if self.workspace is not None else []

    async def get_visible_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Workspace, WorkspaceMember] | None:
        if self.workspace is None or self.membership is None:
            return None
        if self.workspace.id != workspace_id or self.membership.user_id != user_id:
            return None
        return self.workspace, self.membership

    async def save(self, workspace: Workspace) -> Workspace:
        return workspace

    async def archive(self, workspace: Workspace) -> Workspace:
        workspace.status = "archived"
        workspace.archived_at = datetime.now(timezone.utc)
        return workspace

    async def soft_delete(self, workspace: Workspace, membership: WorkspaceMember) -> Workspace:
        workspace.status = "deleted"
        workspace.deleted_at = datetime.now(timezone.utc)
        membership.status = "removed"
        membership.deleted_at = datetime.now(timezone.utc)
        return workspace


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="owner@example.com",
        display_name="Owner",
        password_hash="hash",
        status="active",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.anyio
async def test_create_workspace_creates_owner_membership() -> None:
    db = UnitOfWorkStub()
    repo = WorkspaceRepositoryStub()
    service = WorkspaceService(db, repo)  # type: ignore[arg-type]
    user = make_user()

    workspace, membership = await service.create_workspace(
        user,
        CreateWorkspaceRequest(name="My Project", settings={"sync": "auto"}),
    )

    assert workspace.name == "My Project"
    assert workspace.slug == "my-project"
    assert workspace.owner_id == user.id
    assert workspace.settings == {"sync": "auto"}
    assert membership.role == "owner"
    assert membership.user_id == user.id
    assert db.committed


@pytest.mark.anyio
async def test_update_workspace_requires_owner() -> None:
    db = UnitOfWorkStub()
    repo = WorkspaceRepositoryStub()
    service = WorkspaceService(db, repo)  # type: ignore[arg-type]
    user = make_user()
    workspace, membership = await service.create_workspace(user, CreateWorkspaceRequest(name="Project"))
    membership.role = "developer"

    with pytest.raises(PermissionDenied):
        await service.update_workspace(user, workspace.id, UpdateWorkspaceRequest(name="New Name"))


@pytest.mark.anyio
async def test_get_workspace_requires_visible_membership() -> None:
    db = UnitOfWorkStub()
    repo = WorkspaceRepositoryStub()
    service = WorkspaceService(db, repo)  # type: ignore[arg-type]
    user = make_user()

    with pytest.raises(ResourceNotFound):
        await service.get_workspace(user, uuid.uuid4())


def test_slugify_normalizes_workspace_names() -> None:
    assert slugify(" My Cool Project!! ") == "my-cool-project"
    assert slugify("   ") == "workspace"

