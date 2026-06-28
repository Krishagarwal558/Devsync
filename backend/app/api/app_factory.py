"""FastAPI application factory."""

from __future__ import annotations

import logging
from uuid import UUID

from backend.app.application.auth import (
    LoginCommand,
    LoginUseCase,
    RegisterDeviceCommand,
    RegisterDeviceUseCase,
    RegisterUserCommand,
    RegisterUserUseCase,
    TrustDeviceUseCase,
)
from backend.app.application.sync import SubmitSyncOperationCommand, SubmitSyncOperationUseCase
from backend.app.application.workspaces import CreateWorkspaceCommand, CreateWorkspaceUseCase, ListWorkspacesUseCase
from backend.app.container import BackendContainer, build_container
from backend.app.domain.sync import SyncOperationType
from shared.devsync_shared.errors import AuthenticationError, ConflictError, DevSyncError, NotFoundError


def create_app(container: BackendContainer | None = None):
    """Create and configure the FastAPI application."""
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is not installed. Install project dependencies to run the backend server."
        ) from exc

    services = container or build_container()
    logging.basicConfig(level=services.settings.log_level)
    app = FastAPI(title=services.settings.app_name, version="0.1.0")

    class RegisterUserRequest(BaseModel):
        email: str
        display_name: str
        password: str

    class LoginRequest(BaseModel):
        email: str
        password: str
        device_id: UUID | None = None

    class RegisterDeviceRequest(BaseModel):
        user_id: UUID
        name: str
        public_key: str

    class CreateWorkspaceRequest(BaseModel):
        owner_id: UUID
        name: str

    class SubmitSyncOperationRequest(BaseModel):
        device_id: UUID
        operation_type: SyncOperationType
        path: str
        payload: dict[str, object]

    def handle_error(error: DevSyncError) -> HTTPException:
        """Map domain errors to HTTP exceptions."""
        if isinstance(error, AuthenticationError):
            return HTTPException(status_code=401, detail=str(error))
        if isinstance(error, NotFoundError):
            return HTTPException(status_code=404, detail=str(error))
        if isinstance(error, ConflictError):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=400, detail=str(error))

    @app.get("/v1/health")
    def health() -> dict[str, str]:
        """Return service health."""
        return {"status": "ok", "environment": services.settings.environment}

    @app.post("/v1/auth/register")
    def register_user(request: RegisterUserRequest) -> dict[str, str]:
        """Register a user."""
        try:
            user = RegisterUserUseCase(services.users, services.password_hasher).execute(
                RegisterUserCommand(request.email, request.display_name, request.password)
            )
            return {"id": str(user.id), "email": user.email, "display_name": user.display_name}
        except DevSyncError as error:
            raise handle_error(error) from error

    @app.post("/v1/auth/login")
    def login(request: LoginRequest) -> dict[str, str]:
        """Authenticate a user."""
        try:
            tokens = LoginUseCase(
                services.users,
                services.devices,
                services.password_hasher,
                services.token_service,
            ).execute(LoginCommand(request.email, request.password, request.device_id))
            return {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_at": tokens.expires_at.isoformat(),
            }
        except DevSyncError as error:
            raise handle_error(error) from error

    @app.post("/v1/devices/register")
    def register_device(request: RegisterDeviceRequest) -> dict[str, str]:
        """Register a device."""
        try:
            device = RegisterDeviceUseCase(services.users, services.devices).execute(
                RegisterDeviceCommand(request.user_id, request.name, request.public_key)
            )
            return {"id": str(device.id), "trust_status": device.trust_status.value}
        except DevSyncError as error:
            raise handle_error(error) from error

    @app.post("/v1/devices/{device_id}/trust")
    def trust_device(device_id: UUID) -> dict[str, str]:
        """Trust a registered device."""
        try:
            device = TrustDeviceUseCase(services.devices).execute(device_id)
            return {"id": str(device.id), "trust_status": device.trust_status.value}
        except DevSyncError as error:
            raise handle_error(error) from error

    @app.post("/v1/workspaces")
    def create_workspace(request: CreateWorkspaceRequest) -> dict[str, str]:
        """Create a workspace."""
        try:
            workspace = CreateWorkspaceUseCase(services.users, services.workspaces).execute(
                CreateWorkspaceCommand(request.owner_id, request.name)
            )
            return {"id": str(workspace.id), "name": workspace.name, "status": workspace.status.value}
        except DevSyncError as error:
            raise handle_error(error) from error

    @app.get("/v1/users/{user_id}/workspaces")
    def list_workspaces(user_id: UUID) -> list[dict[str, str]]:
        """List workspaces for a user."""
        workspaces = ListWorkspacesUseCase(services.workspaces).execute(user_id)
        return [
            {"id": str(workspace.id), "name": workspace.name, "status": workspace.status.value}
            for workspace in workspaces
        ]

    @app.post("/v1/workspaces/{workspace_id}/sync/operations")
    def submit_sync_operation(workspace_id: UUID, request: SubmitSyncOperationRequest) -> dict[str, object]:
        """Submit a sync operation through HTTP fallback."""
        try:
            operation = SubmitSyncOperationUseCase(services.workspaces, services.sync_operations).execute(
                SubmitSyncOperationCommand(
                    workspace_id=workspace_id,
                    device_id=request.device_id,
                    operation_type=request.operation_type,
                    path=request.path,
                    payload=request.payload,
                )
            )
            return {"id": str(operation.id), "sequence": operation.sequence}
        except DevSyncError as error:
            raise handle_error(error) from error

    return app

