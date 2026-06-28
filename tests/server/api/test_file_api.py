from __future__ import annotations

import hashlib
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
async def api_client(tmp_path) -> AsyncGenerator[AsyncClient, None]:  # type: ignore[no-untyped-def]
    database_url = os.environ["DEVSYNC_TEST_DATABASE_URL"]
    settings = Settings(
        database_url=database_url,
        jwt_secret_key="api-test-secret-that-is-long-enough",
        bcrypt_rounds=4,
        storage_root=str(tmp_path / "storage"),
        max_upload_bytes=1024 * 1024,
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
    response = await api_client.post("/v1/workspaces", headers=headers, json={"name": "Files Project"})
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
async def test_file_upload_download_restore_and_delete(api_client: AsyncClient) -> None:
    auth_payload = await register_user(api_client)
    headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}
    workspace_id = await create_workspace(api_client, headers)
    device_id = await create_trusted_device(api_client, headers)
    first_content = b"print('one')\n"
    first_checksum = hashlib.sha256(first_content).hexdigest()

    upload_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/files/upload",
        headers=headers,
        data={"path": "src/app.py", "sender_device_id": device_id, "checksum": first_checksum},
        files={"file": ("app.py", first_content, "text/x-python")},
    )
    assert upload_response.status_code == 201
    first_upload = upload_response.json()
    assert first_upload["version_number"] == 1
    assert first_upload["checksum"] == first_checksum

    file_id = first_upload["file_id"]
    version_id = first_upload["version_id"]
    second_content = b"print('two')\n"

    second_upload_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/files/upload",
        headers=headers,
        data={"path": "src/app.py", "sender_device_id": device_id},
        files={"file": ("app.py", second_content, "text/x-python")},
    )
    assert second_upload_response.status_code == 201
    assert second_upload_response.json()["version_number"] == 2

    list_response = await api_client.get(f"/v1/workspaces/{workspace_id}/files", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["path"] == "src/app.py"

    download_response = await api_client.get(f"/v1/workspaces/{workspace_id}/files/{file_id}/download", headers=headers)
    assert download_response.status_code == 200
    assert download_response.content == second_content

    versions_response = await api_client.get(f"/v1/workspaces/{workspace_id}/files/{file_id}/versions", headers=headers)
    assert versions_response.status_code == 200
    assert [version["version_number"] for version in versions_response.json()] == [2, 1]

    restore_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/files/{file_id}/restore",
        headers=headers,
        json={"version_id": version_id, "sender_device_id": device_id},
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["version_number"] == 3

    restored_download_response = await api_client.get(f"/v1/workspaces/{workspace_id}/files/{file_id}/download", headers=headers)
    assert restored_download_response.status_code == 200
    assert restored_download_response.content == first_content

    delete_response = await api_client.delete(f"/v1/workspaces/{workspace_id}/files/{file_id}", headers=headers)
    assert delete_response.status_code == 204

    normal_list_response = await api_client.get(f"/v1/workspaces/{workspace_id}/files", headers=headers)
    assert normal_list_response.status_code == 200
    assert normal_list_response.json()["items"] == []

    deleted_list_response = await api_client.get(f"/v1/workspaces/{workspace_id}/files?include_deleted=true", headers=headers)
    assert deleted_list_response.status_code == 200
    assert len(deleted_list_response.json()["items"]) == 1


@pytest.mark.anyio
async def test_upload_rejects_checksum_mismatch_and_pending_device(api_client: AsyncClient) -> None:
    auth_payload = await register_user(api_client)
    headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}
    workspace_id = await create_workspace(api_client, headers)
    trusted_device_id = await create_trusted_device(api_client, headers)

    mismatch_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/files/upload",
        headers=headers,
        data={"path": "file.txt", "sender_device_id": trusted_device_id, "checksum": "wrong"},
        files={"file": ("file.txt", b"content", "text/plain")},
    )
    assert mismatch_response.status_code == 409

    pending_device_response = await api_client.post(
        "/v1/devices",
        headers=headers,
        json={"name": "Pending Laptop", "platform": "windows"},
    )
    assert pending_device_response.status_code == 201
    pending_device_id = pending_device_response.json()["id"]

    pending_response = await api_client.post(
        f"/v1/workspaces/{workspace_id}/files/upload",
        headers=headers,
        data={"path": "file.txt", "sender_device_id": pending_device_id},
        files={"file": ("file.txt", b"content", "text/plain")},
    )
    assert pending_response.status_code == 403
