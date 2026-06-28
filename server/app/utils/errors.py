"""Application errors and HTTP error mapping."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass(frozen=True)
class AppError(Exception):
    """Base expected application error."""

    message: str
    status_code: int = 400
    code: str = "bad_request"


class AuthenticationFailed(AppError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message=message, status_code=401, code="authentication_failed")


class PermissionDenied(AppError):
    """Raised when a request is authenticated but not allowed."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message=message, status_code=403, code="permission_denied")


class ResourceConflict(AppError):
    """Raised when a requested change conflicts with existing state."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=409, code="resource_conflict")


class ResourceNotFound(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message=message, status_code=404, code="not_found")


def install_error_handlers(app: FastAPI) -> None:
    """Install consistent application error responses."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        response = JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "")
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        response = JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Request payload is invalid", "request_id": request_id}},
        )
        response.headers["X-Request-ID"] = request_id or ""
        return response

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        response = JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail), "request_id": request_id}},
        )
        response.headers["X-Request-ID"] = request_id or ""
        return response
