from __future__ import annotations

import asyncio

import pytest

from desktop.app.core.websocket_client import RealtimeWebSocketClient


class ReconnectClient(RealtimeWebSocketClient):
    def __init__(self) -> None:
        super().__init__("http://localhost:8000", "token", "workspace", "device", 0, self.on_message)
        self.attempts = 0

    async def on_message(self, message: dict[str, object]) -> None:
        return None

    async def _connect_once(self) -> None:  # type: ignore[override]
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("network down")
        await self.stop()


@pytest.mark.anyio
async def test_websocket_client_reconnects_after_disconnect(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = ReconnectClient()

    async def fast_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    await client.run_forever()

    assert client.attempts == 2
