"""WebSocket realtime client."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import websockets

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, object]], Awaitable[None]]


class RealtimeWebSocketClient:
    """Reconnectable realtime WebSocket client."""

    def __init__(
        self,
        server_url: str,
        access_token: str,
        workspace_id: str,
        device_id: str,
        last_sequence: int,
        on_message: MessageHandler,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._access_token = access_token
        self._workspace_id = workspace_id
        self._device_id = device_id
        self._last_sequence = last_sequence
        self._on_message = on_message
        self._running = False
        self._websocket = None

    async def run_forever(self) -> None:
        """Connect and reconnect until stopped."""
        self._running = True
        while self._running:
            try:
                await self._connect_once()
            except Exception as exc:  # noqa: BLE001
                logger.warning("WebSocket disconnected: %s", exc)
                await asyncio.sleep(2)

    async def stop(self) -> None:
        """Stop the realtime client."""
        self._running = False
        if self._websocket is not None:
            await self._websocket.close()

    async def send_ack(self, sequence: int) -> None:
        """Send ack over WebSocket if connected."""
        if self._websocket is not None:
            await self._websocket.send(json.dumps({"type": "sync_ack", "workspace_id": self._workspace_id, "sequence": sequence}))

    async def heartbeat(self) -> None:
        """Send heartbeat over WebSocket if connected."""
        if self._websocket is not None:
            await self._websocket.send(
                json.dumps({"type": "device_heartbeat", "workspace_id": self._workspace_id, "device_id": self._device_id})
            )

    async def _connect_once(self) -> None:
        ws_url = self._server_url.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/v1/ws?token={self._access_token}"
        async with websockets.connect(uri) as websocket:
            self._websocket = websocket
            await websocket.send(
                json.dumps(
                    {
                        "type": "workspace_join",
                        "workspace_id": self._workspace_id,
                        "device_id": self._device_id,
                        "last_sequence": self._last_sequence,
                    }
                )
            )
            async for raw_message in websocket:
                message = json.loads(raw_message)
                if isinstance(message, dict):
                    await self._on_message(message)

