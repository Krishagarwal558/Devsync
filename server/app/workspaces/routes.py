"""Workspace API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from server.app.auth.dependencies import get_current_user
from server.app.auth.models import User
from server.app.workspaces.dependencies import get_workspace_service
from server.app.workspaces.schemas import (
    CreateWorkspaceRequest,
    UpdateWorkspaceRequest,
    WorkspaceDetailResponse,
    WorkspaceResponse,
)
from server.app.workspaces.services import WorkspaceService

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceDetailResponse:
    """Create a workspace owned by the current user."""
    workspace, membership = await workspace_service.create_workspace(current_user, request)
    return WorkspaceDetailResponse.model_validate({**workspace.__dict__, "membership": membership})


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    include_archived: Annotated[bool, Query()] = False,
    include_deleted: Annotated[bool, Query()] = False,
) -> list[WorkspaceResponse]:
    """List workspaces visible to the current user."""
    workspaces = await workspace_service.list_workspaces(
        current_user,
        include_archived=include_archived,
        include_deleted=include_deleted,
    )
    return [WorkspaceResponse.model_validate(workspace) for workspace in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceDetailResponse:
    """Get workspace details."""
    workspace, membership = await workspace_service.get_workspace(current_user, workspace_id)
    return WorkspaceDetailResponse.model_validate({**workspace.__dict__, "membership": membership})


@router.patch("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def update_workspace(
    workspace_id: UUID,
    request: UpdateWorkspaceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceDetailResponse:
    """Rename a workspace or update settings."""
    workspace, membership = await workspace_service.update_workspace(current_user, workspace_id, request)
    return WorkspaceDetailResponse.model_validate({**workspace.__dict__, "membership": membership})


@router.post("/{workspace_id}/archive", response_model=WorkspaceDetailResponse)
async def archive_workspace(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceDetailResponse:
    """Archive a workspace."""
    workspace, membership = await workspace_service.archive_workspace(current_user, workspace_id)
    return WorkspaceDetailResponse.model_validate({**workspace.__dict__, "membership": membership})


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Soft delete a workspace."""
    await workspace_service.delete_workspace(current_user, workspace_id)

