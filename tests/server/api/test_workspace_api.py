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


@pytest.mark.anyio
async def test_workspace_lifecycle(api_client: AsyncClient) -> None:
    auth_payload = await register_user(api_client)
    headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}

    create_response = await api_client.post(
        "/v1/workspaces",
        headers=headers,
        json={"name": "Game Project", "settings": {"auto_sync": True}},
    )
    assert create_response.status_code == 201
    workspace = create_response.json()
    assert workspace["name"] == "Game Project"
    assert workspace["slug"] == "game-project"
    assert workspace["membership"]["role"] == "owner"

    list_response = await api_client.get("/v1/workspaces", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    details_response = await api_client.get(f"/v1/workspaces/{workspace['id']}", headers=headers)
    assert details_response.status_code == 200
    assert details_response.json()["id"] == workspace["id"]

    update_response = await api_client.patch(
        f"/v1/workspaces/{workspace['id']}",
        headers=headers,
        json={"name": "Renamed Project", "settings": {"auto_sync": False}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["slug"] == "renamed-project"
    assert update_response.json()["settings"] == {"auto_sync": False}

    archive_response = await api_client.post(f"/v1/workspaces/{workspace['id']}/archive", headers=headers)
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    normal_list_response = await api_client.get("/v1/workspaces", headers=headers)
    assert normal_list_response.status_code == 200
    assert normal_list_response.json() == []

    archived_list_response = await api_client.get("/v1/workspaces?include_archived=true", headers=headers)
    assert archived_list_response.status_code == 200
    assert len(archived_list_response.json()) == 1

    delete_response = await api_client.delete(f"/v1/workspaces/{workspace['id']}", headers=headers)
    assert delete_response.status_code == 204

    deleted_details_response = await api_client.get(f"/v1/workspaces/{workspace['id']}", headers=headers)
    assert deleted_details_response.status_code == 404


@pytest.mark.anyio
async def test_user_cannot_see_another_users_workspace(api_client: AsyncClient) -> None:
    owner_payload = await register_user(api_client, "owner@example.com")
    other_payload = await register_user(api_client, "other@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_payload['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other_payload['access_token']}"}

    create_response = await api_client.post(
        "/v1/workspaces",
        headers=owner_headers,
        json={"name": "Private Project"},
    )
    assert create_response.status_code == 201
    workspace_id = create_response.json()["id"]

    forbidden_response = await api_client.get(f"/v1/workspaces/{workspace_id}", headers=other_headers)
    assert forbidden_response.status_code == 404

