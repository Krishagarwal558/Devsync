"""Synchronization event service workflows."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.auth.models import User
from server.app.devices.models import Device
from server.app.devices.repositories import DeviceRepository
from server.app.sync.models import SyncEvent
from server.app.sync.repositories import SyncEventRepository
from server.app.sync.schemas import (
    AcknowledgeSyncEventsRequest,
    CreateSyncEventRequest,
    SyncEventPayload,
    SyncEventType,
)
from server.app.utils.errors import PermissionDenied, ResourceConflict, ResourceNotFound
from server.app.websocket.events import realtime_dispatcher
from server.app.workspaces.models import Workspace
from server.app.workspaces.repositories import WorkspaceRepository

logger = logging.getLogger(__name__)


class SyncEventService:
    """Synchronization protocol use cases."""

    def __init__(
        self,
        db: AsyncSession,
        sync_repository: SyncEventRepository,
        workspace_repository: WorkspaceRepository,
        device_repository: DeviceRepository,
    ) -> None:
        """Create service."""
        self._db = db
        self._sync_repository = sync_repository
        self._workspace_repository = workspace_repository
        self._device_repository = device_repository

    async def create_event(self, current_user: User, workspace_id: UUID, request: CreateSyncEventRequest) -> SyncEvent:
        """Validate, sequence, and persist a synchronization event."""
        workspace = await self._require_active_workspace(current_user, workspace_id)
        await self._require_trusted_device(current_user, request.sender_device_id)
        self._validate_event_path(request.path)
        self._validate_payload_paths(request.payload)

        payload = request.payload.model_dump(mode="json", exclude_none=True)
        duplicate = await self._sync_repository.find_duplicate(
            workspace_id=workspace.id,
            sender_device_id=request.sender_device_id,
            event_type=request.event_type.value,
            path=request.path,
            payload=payload,
            checksum=request.checksum,
        )
        if duplicate is not None:
            raise ResourceConflict("Duplicate synchronization event")

        try:
            await self._sync_repository.lock_workspace_for_sequence(workspace.id)
            sequence = await self._sync_repository.next_sequence(workspace.id)
            event = await self._sync_repository.create_event(
                workspace_id=workspace.id,
                sender_device_id=request.sender_device_id,
                sequence=sequence,
                event_type=request.event_type.value,
                path=request.path,
                payload=payload,
                checksum=request.checksum,
                bandwidth_bytes=request.bandwidth_bytes,
            )
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise ResourceConflict("Synchronization event sequence conflict") from exc

        await realtime_dispatcher.publish_sync_event(event, sender_device_id=request.sender_device_id)
        logger.info("Created sync event %s:%s by device %s", workspace.id, event.sequence, request.sender_device_id)
        return event

    async def list_events(
        self,
        current_user: User,
        workspace_id: UUID,
        limit: int,
        offset: int,
        after_sequence: int | None = None,
    ) -> list[SyncEvent]:
        """Return ordered synchronization history."""
        workspace = await self._require_member_workspace(current_user, workspace_id)
        return await self._sync_repository.list_events(workspace.id, limit=limit, offset=offset, after_sequence=after_sequence)

    async def replay_events(self, current_user: User, workspace_id: UUID, after_sequence: int, limit: int) -> list[SyncEvent]:
        """Return events after a processed sequence number."""
        workspace = await self._require_member_workspace(current_user, workspace_id)
        return await self._sync_repository.replay_events(workspace.id, after_sequence=after_sequence, limit=limit)

    async def acknowledge_events(
        self,
        current_user: User,
        workspace_id: UUID,
        request: AcknowledgeSyncEventsRequest,
    ) -> int:
        """Process event acknowledgement metadata."""
        workspace = await self._require_active_workspace(current_user, workspace_id)
        await self._require_trusted_device(current_user, request.device_id)
        if request.event_ids is not None:
            count = await self._sync_repository.acknowledge_by_ids(workspace.id, request.event_ids)
        else:
            count = await self._sync_repository.acknowledge_up_to_sequence(workspace.id, request.up_to_sequence or 0)
        await self._db.commit()
        logger.info("Acknowledged %s sync events in workspace %s", count, workspace.id)
        return count

    async def _require_member_workspace(self, current_user: User, workspace_id: UUID) -> Workspace:
        """Require active workspace membership."""
        result = await self._workspace_repository.get_visible_workspace(workspace_id, current_user.id)
        if result is None:
            raise ResourceNotFound("Workspace not found")
        return result[0]

    async def _require_active_workspace(self, current_user: User, workspace_id: UUID) -> Workspace:
        """Require workspace membership and active workspace status."""
        workspace = await self._require_member_workspace(current_user, workspace_id)
        if workspace.status != "active" or workspace.deleted_at is not None:
            raise ResourceConflict("Workspace is not active")
        return workspace

    async def _require_trusted_device(self, current_user: User, device_id: UUID) -> Device:
        """Require an owned trusted device."""
        device = await self._device_repository.get_for_user(device_id, current_user.id)
        if device is None:
            raise ResourceNotFound("Device not found")
        if device.trust_status != "trusted" or device.deleted_at is not None:
            raise PermissionDenied("Trusted device required")
        return device

    def _validate_payload_paths(self, payload: SyncEventPayload) -> None:
        """Validate optional payload paths."""
        if payload.source_path is not None:
            self._validate_event_path(payload.source_path)
        if payload.target_path is not None:
            self._validate_event_path(payload.target_path)

    def _validate_event_path(self, path: str) -> None:
        """Reject unsafe or invalid client paths."""
        if path.startswith("/") or path.startswith("\\") or ":" in path:
            raise ResourceConflict("Path must be relative")
        parts = [part for part in path.replace("\\", "/").split("/") if part]
        if not parts or any(part == ".." for part in parts):
            raise ResourceConflict("Path is invalid")


def supported_event_types() -> list[str]:
    """Return supported event type values."""
    return [event_type.value for event_type in SyncEventType]
