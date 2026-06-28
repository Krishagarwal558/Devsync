"""Authentication API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from server.app.auth.dependencies import get_auth_service, get_current_user
from server.app.auth.models import User
from server.app.auth.schemas import AuthResponse, LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, UserResponse
from server.app.auth.services import AuthService

router = APIRouter(prefix="/v1", tags=["authentication"])


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Register a user."""
    return await auth_service.register(request)


@router.post("/auth/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Login with email and password."""
    return await auth_service.login(request)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    """Logout by revoking a refresh token session."""
    await auth_service.logout(request)


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh(
    request: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Rotate refresh token and issue a new access token."""
    return await auth_service.refresh(request)


@router.get("/users/me", response_model=UserResponse)
async def users_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return current authenticated user."""
    return current_user

