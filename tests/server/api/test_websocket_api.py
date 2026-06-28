from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.app.auth.dependencies import get_token_service
from server.app.auth.security import TokenService
from server.app.config.settings import Settings, get_settings
from server.app.database.base import Base
from server.app.database.session import get_db_session
from server.app.main import create_app

pytestmark = pytest.mark.skipif(
    not os.getenv("DEVSYNC_TEST_DATABASE_URL"),
    reason="DEVSYNC_TEST_DATABASE_URL is required for PostgreSQL WebSocket API tests",
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    database_url = os.environ["DEVSYNC_TEST_DATABASE_URL"]
    settings = Settings(
        database_url=database_url,
        jwt_secret_key="api-test-secret-that-is-long-enough",
        bcrypt_rounds=4,
    )
    get_settings.cache_clear()
    app = create_app()
    engine = create_async_engine(database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def reset_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    import anyio

    anyio.run(reset_database)

    async def test_db_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_token_service] = lambda: TokenService(settings)
    app.dependency_overrides[get_db_session] = test_db_session

    with TestClient(app) as test_client:
        yield test_client

    anyio.run(engine.dispose)
    get_settings.cache_clear()


def register_user(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/v1/auth/register",
        json={"email": "owner@example.com", "password": "strong-password-123", "display_name": "Owner"},
    )
    assert response.status_code == 201
    return response.json()


def test_websocket_join_replay_and_broadcast(client: TestClient) -> None:
    auth_payload = register_user(client)
    headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}
    workspace_response = client.post("/v1/workspaces", headers=headers, json={"name": "Realtime Project"})
    assert workspace_response.status_code == 201
    workspace_id = workspace_response.json()["id"]
    device_response = client.post("/v1/devices", headers=headers, json={"name": "Laptop", "platform": "windows"})
    assert device_response.status_code == 201
    device_id = device_response.json()["id"]
    assert client.post(f"/v1/devices/{device_id}/trust", headers=headers).status_code == 200

    with client.websocket_connect(f"/v1/ws?token={auth_payload['access_token']}") as websocket:
        websocket.send_json(
            {
                "type": "workspace_join",
                "workspace_id": workspace_id,
                "device_id": device_id,
                "last_sequence": 0,
            }
        )
        joined = websocket.receive_json()
        assert joined["type"] == "workspace_joined"
        assert joined["replayed_events"] == 0

        event_response = client.post(
            f"/v1/workspaces/{workspace_id}/sync/events",
            headers=headers,
            json={"sender_device_id": device_id, "event_type": "file_modified", "path": "src/app.py"},
        )
        assert event_response.status_code == 201

