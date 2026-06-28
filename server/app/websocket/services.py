"""WebSocket gateway service workflows."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket, WebSocketDisconnect

from server.app.auth.models import User
from server.app.auth.repositories import AuthRepository
from server.app.auth.security import TokenService
from server.app.devices.models import Device
from server.app.devices.repositories import DeviceRepository
from server.app.sync.repositories import SyncEventRepository
from server.app.utils.errors import AppError, AuthenticationFailed, PermissionDenied, ResourceConflict, ResourceNotFound
from server.app.websocket.events import sync_event_to_message
from server.app.websocket.manager import WebSocketConnection, WebSocketManager
from server.app.websocket.schemas import (
    ClientEventType,
    DeviceHeartbeatMessage,
    SyncAckMessage,
    WorkspaceJoinMessage,
    WorkspaceJoinedEvent,
    WorkspaceLeaveMessage,
)
from server.app.workspaces.models import Workspace
from server.app.workspaces.repositories import WorkspaceRepository

logger = logging.getLogger(__name__)


class WebSocketGatewayService:
    """Coordinates realtime WebSocket workflows."""

    def __init__(
        self,
        db: AsyncSession,
        token_service: TokenService,
        auth_repository: AuthRepository,
        workspace_repository: WorkspaceRepository,
        device_repository: DeviceRepository,
        sync_repository: SyncEventRepository,
        manager: WebSocketManager,
    ) -> None:
        """Create gateway service."""
        self._db = db
        self._token_service = token_service
        self._auth_repository = auth_repository
        self._workspace_repository = workspace_repository
        self._device_repository = device_repository
        self._sync_repository = sync_repository
        self._manager = manager

    async def authenticate(self, access_token: str | None) -> User:
        """Authenticate a WebSocket access token."""
        if not access_token:
            raise AuthenticationFailed("Authentication is required")
        token_payload = self._token_service.decode_access_token(access_token)
        user_id = UUID(token_payload["sub"])
        session_id = UUID(token_payload["sid"])
        session = await self._auth_repository.get_active_session_by_id(session_id)
        if session is None or session.user_id != user_id:
            raise AuthenticationFailed("Session is no longer active")
        user = await self._auth_repository.get_user_by_id(user_id)
        if user is None or user.status != "active":
            raise AuthenticationFailed("User is no longer active")
        return user

    async def serve(self, websocket: WebSocket, current_user: User) -> None:
        """Accept and serve a WebSocket connection."""
        connection = await self._manager.connect(websocket, current_user.id)
        try:
            while True:
                raw_message = await websocket.receive_text()
                await self.handle_raw_message(connection, current_user, raw_message)
        except WebSocketDisconnect:
            await self._manager.disconnect(connection)
        except Exception:
            logger.exception("Unexpected WebSocket gateway failure")
            await self._manager.disconnect(connection)

    async def handle_raw_message(self, connection: WebSocketConnection, current_user: User, raw_message: str) -> None:
        """Parse and handle a raw client message."""
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._manager.send_error(connection, "invalid_json", "Message must be valid JSON.")
            return
        message_type = payload.get("type")
        try:
            if message_type == ClientEventType.WORKSPACE_JOIN:
                await self.join_workspace(connection, current_user, WorkspaceJoinMessage.model_validate(payload))
            elif message_type == ClientEventType.WORKSPACE_LEAVE:
                await self.leave_workspace(connection, WorkspaceLeaveMessage.model_validate(payload))
            elif message_type == ClientEventType.DEVICE_HEARTBEAT:
                await self.device_heartbeat(connection, current_user, DeviceHeartbeatMessage.model_validate(payload))
            elif message_type == ClientEventType.SYNC_ACK:
                await self.sync_ack(connection, current_user, SyncAckMessage.model_validate(payload))
            else:
                await self._manager.send_error(connection, "unknown_event", "Unsupported WebSocket event type.")
        except ValidationError:
            await self._manager.send_error(connection, "invalid_message", "Message payload is invalid.")
        except AppError as exc:
            await self._manager.send_error(connection, exc.code, exc.message)

    async def join_workspace(self, connection: WebSocketConnection, current_user: User, message: WorkspaceJoinMessage) -> None:
        """Validate and join a workspace room."""
        workspace = await self._require_active_workspace(current_user, message.workspace_id)
        device = await self._require_trusted_device(current_user, message.device_id)
        replay_events = await self._sync_repository.replay_events(workspace.id, after_sequence=message.last_sequence, limit=500)
        await self._manager.join_workspace(connection, workspace.id, device.id, device.name)
        for event in replay_events:
            if event.sender_device_id != device.id:
                await self._manager.send(connection, sync_event_to_message(event))
        await self._manager.send(
            connection,
            WorkspaceJoinedEvent(
                workspace_id=workspace.id,
                replayed_events=len([event for event in replay_events if event.sender_device_id != device.id]),
            ).model_dump(mode="json"),
        )

    async def leave_workspace(self, connection: WebSocketConnection, message: WorkspaceLeaveMessage) -> None:
        """Leave a workspace room."""
        await self._manager.leave_workspace(connection, message.workspace_id)

    async def device_heartbeat(self, connection: WebSocketConnection, current_user: User, message: DeviceHeartbeatMessage) -> None:
        """Update connection and device heartbeat."""
        if message.workspace_id not in connection.joined_workspaces:
            raise ResourceNotFound("Workspace not joined")
        device = await self._require_trusted_device(current_user, message.device_id)
        repository_device = await self._device_repository.heartbeat(device)
        await self._db.commit()
        await self._manager.touch_heartbeat(connection)
        logger.info("WebSocket heartbeat from device %s", repository_device.id)

    async def sync_ack(self, connection: WebSocketConnection, current_user: User, message: SyncAckMessage) -> None:
        """Acknowledge sync events for a joined workspace."""
        if message.workspace_id not in connection.joined_workspaces:
            raise ResourceNotFound("Workspace not joined")
        device_id = connection.workspace_devices.get(message.workspace_id)
        if device_id is None:
            raise ResourceNotFound("Device not joined")
        await self._require_trusted_device(current_user, device_id)
        await self._sync_repository.acknowledge_up_to_sequence(message.workspace_id, message.sequence)
        await self._db.commit()

    async def _require_active_workspace(self, current_user: User, workspace_id: UUID) -> Workspace:
        """Require active membership and active workspace status."""
        result = await self._workspace_repository.get_visible_workspace(workspace_id, current_user.id)
        if result is None:
            raise ResourceNotFound("Workspace not found")
        workspace = result[0]
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

