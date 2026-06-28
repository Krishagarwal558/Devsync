"""WebSocket gateway route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from server.app.auth.repositories import AuthRepository
from server.app.auth.security import TokenService
from server.app.config.settings import Settings, get_settings
from server.app.database.session import get_db_session
from server.app.devices.repositories import DeviceRepository
from server.app.sync.repositories import SyncEventRepository
from server.app.utils.errors import AuthenticationFailed
from server.app.websocket.events import realtime_dispatcher
from server.app.websocket.manager import websocket_manager
from server.app.websocket.services import WebSocketGatewayService
from server.app.workspaces.repositories import WorkspaceRepository

router = APIRouter(tags=["websocket"])
realtime_dispatcher.bind_manager(websocket_manager)


@router.websocket("/v1/ws")
async def websocket_gateway(
    websocket: WebSocket,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Serve realtime DevSync WebSocket connections."""
    service = WebSocketGatewayService(
        db=db,
        token_service=TokenService(settings),
        auth_repository=AuthRepository(db),
        workspace_repository=WorkspaceRepository(db),
        device_repository=DeviceRepository(db),
        sync_repository=SyncEventRepository(db),
        manager=websocket_manager,
    )
    try:
        current_user = await service.authenticate(websocket.query_params.get("token"))
    except AuthenticationFailed:
        await websocket.close(code=4401, reason="Authentication failed")
        return
    await service.serve(websocket, current_user)
    if websocket.client_state != WebSocketState.DISCONNECTED:
        await websocket.close()
