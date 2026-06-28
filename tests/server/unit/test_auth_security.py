from __future__ import annotations

from uuid import uuid4

import pytest

from server.app.auth.security import PasswordHasher, TokenService
from server.app.config.settings import Settings
from server.app.utils.errors import AuthenticationFailed


def test_password_hasher_hashes_and_verifies_password() -> None:
    hasher = PasswordHasher(bcrypt_rounds=4)

    password_hash = hasher.hash_password("strong-password-123")

    assert password_hash != "strong-password-123"
    assert hasher.verify_password("strong-password-123", password_hash)
    assert not hasher.verify_password("wrong-password", password_hash)


def test_token_service_issues_and_validates_access_token() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://devsync:devsync@localhost:5432/devsync",
        jwt_secret_key="unit-test-secret-that-is-long-enough",
        access_token_minutes=15,
    )
    token_service = TokenService(settings)
    user_id = uuid4()
    session_id = uuid4()

    token = token_service.create_access_token(user_id=user_id, session_id=session_id)
    payload = token_service.decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["sid"] == str(session_id)


def test_token_service_rejects_invalid_access_token() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://devsync:devsync@localhost:5432/devsync",
        jwt_secret_key="unit-test-secret-that-is-long-enough",
    )
    token_service = TokenService(settings)

    with pytest.raises(AuthenticationFailed):
        token_service.decode_access_token("not-a-valid-token")


def test_refresh_tokens_are_opaque_and_hashed() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://devsync:devsync@localhost:5432/devsync",
        jwt_secret_key="unit-test-secret-that-is-long-enough",
    )
    token_service = TokenService(settings)

    refresh_token = token_service.create_refresh_token()
    refresh_hash = token_service.hash_refresh_token(refresh_token)

    assert len(refresh_token) >= 32
    assert refresh_hash != refresh_token
    assert token_service.hash_refresh_token(refresh_token) == refresh_hash


def test_beta_requires_r2_storage() -> None:
    with pytest.raises(ValueError, match="DEVSYNC_STORAGE_PROVIDER must be r2"):
        Settings(
            environment="beta",
            database_url="postgresql+asyncpg://devsync:devsync@localhost:5432/devsync",
            jwt_secret_key="unit-test-secret-that-is-long-enough",
            storage_provider="local",
        )


def test_r2_storage_requires_credentials() -> None:
    with pytest.raises(ValueError, match="Missing R2 settings"):
        Settings(
            environment="development",
            database_url="postgresql+asyncpg://devsync:devsync@localhost:5432/devsync",
            jwt_secret_key="unit-test-secret-that-is-long-enough",
            storage_provider="r2",
        )
