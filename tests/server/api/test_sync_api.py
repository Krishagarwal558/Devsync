from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.app.auth.dependencies import get_token_service
from server.app.auth.security import TokenService
from server.app.config.settings import Settings, get_settings
from server.app.database.base import Base
from server.app.database.session import get_db_session
from server.app.main import create_app

pytestmark = pytest.mark.skipif(
    not os.getenv("DEVSYNC_TEST_DATABASE_URL"),
    reason="DEVSYNC_TEST_DATABASE_URL is required for PostgreSQL API tests",
)


@pytest.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
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

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_token_service] = lambda: TokenService(settings)
    app.dependency_overrides[get_db_session] = test_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await engine.dispose()
    get_settings.cache_clear()


async def register_user(api_client: AsyncClient, email: str = "owner@example.com") -> dict[str, object]:
    response = await api_client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": "strong-password-123",
            "display_name": "Owner",
        },
    )
    assert response.status_code == 201
    return response.json()


async def create_workspace(api_client: AsyncClient, headers: dict[str, str]) -> str:
    response = await api_client.post("/v1/workspaces", headers=headers, json={"name": "Sync Project"})
    assert response.status_code == 201
    return str(response.json()["id"])


async def create_trusted_device(api_client: AsyncClient, headers: dict[str, str]) -> str:
    response = await api_client.post(
        "/v1/devices",
        headers=headers,
        json={"name": "Laptop", "platform": "windows", "public_key": "key"},
    )
    assert response.status_code == 201
    device_id = str(response.json()["id"])
    trust_response = await api_client.post(f"/v1/devices/{device_id}/trust", headers=headers)
    assert trust_response.status_code == 200
    return device_id


@pytest.mark.anyio
async def test_sync_event_lifecycle(api_client: AsyncClient) -> None:
    auth_payload = await register_user(api_client)
    headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}
    workspace_id = await create_workspace(api_client, headers)
    device_id = await create_trusted_device(api_client, headers)

    first_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/sync/events",
        headers=headers,
        json={
            "sender_device_id": device_id,
            "event_type": "file_created",
            "path": "src/app.py",
            "checksum": "abc",
            "bandwidth_bytes": 128,
            "payload": {"file_size": 128, "metadata": {"language": "python"}},
        },
    )
    assert first_response.status_code == 201
    first = first_response.json()
    assert first["sequence"] == 1
    assert first["status"] == "accepted"

    second_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/sync/events",
        headers=headers,
        json={
            "sender_device_id": device_id,
            "event_type": "file_modified",
            "path": "src/app.py",
            "checksum": "def",
            "payload": {"file_size": 256},
        },
    )
    assert second_response.status_code == 201
    assert second_response.json()["sequence"] == 2

    duplicate_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/sync/events",
        headers=headers,
        json={
            "sender_device_id": device_id,
            "event_type": "file_modified",
            "path": "src/app.py",
            "checksum": "def",
            "payload": {"file_size": 256},
        },
    )
    assert duplicate_response.status_code == 409

    page_response = await api_client.get(f"/v1/workspaces/{workspace_id}/sync/events?limit=1&offset=1", headers=headers)
    assert page_response.status_code == 200
    page = page_response.json()
    assert page["items"][0]["sequence"] == 2

    replay_response = await api_client.get(
        f"/v1/workspaces/{workspace_id}/sync/events/replay?after_sequence=1",
        headers=headers,
    )
    assert replay_response.status_code == 200
    assert [event["sequence"] for event in replay_response.json()["items"]] == [2]

    ack_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/sync/ack",
        headers=headers,
        json={"device_id": device_id, "up_to_sequence": 2},
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["acknowledged_count"] == 2


@pytest.mark.anyio
async def test_sync_event_requires_trusted_owned_device(api_client: AsyncClient) -> None:
    auth_payload = await register_user(api_client)
    headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}
    workspace_id = await create_workspace(api_client, headers)

    pending_device_response = await api_client.post(
        "/v1/devices",
        headers=headers,
        json={"name": "Pending Laptop", "platform": "windows"},
    )
    assert pending_device_response.status_code == 201
    pending_device_id = pending_device_response.json()["id"]

    response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/sync/events",
        headers=headers,
        json={
            "sender_device_id": pending_device_id,
            "event_type": "file_created",
            "path": "file.txt",
        },
    )
    assert response.status_code == 403

