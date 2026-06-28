from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.app.auth.dependencies import get_token_service
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
    app.dependency_overrides[get_token_service] = lambda: __import__(
        "server.app.auth.security",
        fromlist=["TokenService"],
    ).TokenService(settings)
    app.dependency_overrides[get_db_session] = test_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await engine.dispose()
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_register_login_me_refresh_and_logout(api_client: AsyncClient) -> None:
    register_response = await api_client.post(
        "/v1/auth/register",
        json={
            "email": "shrey@example.com",
            "password": "strong-password-123",
            "display_name": "Shrey",
        },
    )
    assert register_response.status_code == 201
    register_payload = register_response.json()
    assert register_payload["user"]["email"] == "shrey@example.com"
    assert register_payload["access_token"]
    assert register_payload["refresh_token"]

    me_response = await api_client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "shrey@example.com"

    login_response = await api_client.post(
        "/v1/auth/login",
        json={"email": "shrey@example.com", "password": "strong-password-123"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()

    refresh_response = await api_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["refresh_token"] != login_payload["refresh_token"]

    reused_refresh_response = await api_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert reused_refresh_response.status_code == 401

    logout_response = await api_client.post(
        "/v1/auth/logout",
        json={"refresh_token": refresh_payload["refresh_token"]},
    )
    assert logout_response.status_code == 204


@pytest.mark.anyio
async def test_register_duplicate_email_returns_conflict(api_client: AsyncClient) -> None:
    payload = {
        "email": "duplicate@example.com",
        "password": "strong-password-123",
        "display_name": "Duplicate",
    }

    first_response = await api_client.post("/v1/auth/register", json=payload)
    second_response = await api_client.post("/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409

