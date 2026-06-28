"""File storage API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from server.app.auth.dependencies import get_current_user
from server.app.auth.models import User
from server.app.files.dependencies import get_file_storage_service
from server.app.files.schemas import (
    FileUploadResponse,
    FileVersionResponse,
    RestoreFileVersionRequest,
    StoredFilePage,
    StoredFileResponse,
)
from server.app.files.services import FileStorageService
from server.app.config.settings import Settings, get_settings
from server.app.utils.errors import ResourceConflict

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    workspace_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    file_service: Annotated[FileStorageService, Depends(get_file_storage_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    path: Annotated[str, Form()],
    sender_device_id: Annotated[UUID, Form()],
    checksum: Annotated[str | None, Form()] = None,
    file_type: Annotated[str, Form()] = "file",
) -> FileUploadResponse:
    """Upload or replace a workspace file."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise ResourceConflict("Invalid Content-Length header") from exc
        if declared_size > settings.max_upload_bytes + 4096:
            raise ResourceConflict("Upload exceeds configured size limit")
    stored_file, version = await file_service.upload_file(
        current_user=current_user,
        workspace_id=workspace_id,
        path=path,
        sender_device_id=sender_device_id,
        stream=file.file,
        checksum=checksum,
        file_type=file_type,
    )
    return FileUploadResponse(
        file_id=stored_file.id,
        version_id=version.id,
        path=stored_file.path,
        version_number=version.version_number,
        checksum=version.content_checksum,
        size_bytes=version.size_bytes,
    )


@router.get("", response_model=StoredFilePage)
async def list_files(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    file_service: Annotated[FileStorageService, Depends(get_file_storage_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_deleted: Annotated[bool, Query()] = False,
    prefix: Annotated[str | None, Query(max_length=2048)] = None,
) -> StoredFilePage:
    """List workspace files."""
    files = await file_service.list_files(
        current_user=current_user,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
        prefix=prefix,
    )
    next_offset = offset + limit if len(files) == limit else None
    return StoredFilePage(
        items=[StoredFileResponse.model_validate(stored_file) for stored_file in files],
        limit=limit,
        offset=offset,
        next_offset=next_offset,
    )


@router.get("/{file_id}/download")
async def download_file(
    workspace_id: UUID,
    file_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    file_service: Annotated[FileStorageService, Depends(get_file_storage_service)],
) -> StreamingResponse:
    """Download the current file version."""
    download = await file_service.download_file(current_user, workspace_id, file_id)
    headers = {
        "Content-Disposition": f'attachment; filename="{download.file_name}"',
        "X-Content-Checksum": download.checksum,
        "Content-Length": str(download.size_bytes),
    }
    return StreamingResponse(
        download.stream,  # type: ignore[arg-type]
        media_type="application/octet-stream",
        headers=headers,
        background=BackgroundTask(download.stream.close),  # type: ignore[attr-defined]
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    workspace_id: UUID,
    file_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    file_service: Annotated[FileStorageService, Depends(get_file_storage_service)],
) -> None:
    """Soft delete a workspace file."""
    await file_service.delete_file(current_user, workspace_id, file_id)


@router.get("/{file_id}/versions", response_model=list[FileVersionResponse])
async def list_file_versions(
    workspace_id: UUID,
    file_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    file_service: Annotated[FileStorageService, Depends(get_file_storage_service)],
) -> list[FileVersionResponse]:
    """Return file version history."""
    versions = await file_service.list_versions(current_user, workspace_id, file_id)
    return [FileVersionResponse.model_validate(version) for version in versions]


@router.post("/{file_id}/restore", response_model=FileUploadResponse)
async def restore_file_version(
    workspace_id: UUID,
    file_id: UUID,
    request: RestoreFileVersionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    file_service: Annotated[FileStorageService, Depends(get_file_storage_service)],
) -> FileUploadResponse:
    """Restore a previous file version."""
    stored_file, version = await file_service.restore_version(current_user, workspace_id, file_id, request)
    return FileUploadResponse(
        file_id=stored_file.id,
        version_id=version.id,
        path=stored_file.path,
        version_number=version.version_number,
        checksum=version.content_checksum,
        size_bytes=version.size_bytes,
    )
