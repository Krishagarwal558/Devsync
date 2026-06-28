"""FastAPI entry point for DevSync Cloud."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.app.auth.routes import router as auth_router
from server.app.config.logging import configure_logging
from server.app.config.settings import get_settings
from server.app.devices.routes import router as devices_router
from server.app.files.routes import router as files_router
from server.app.middleware.request_id import request_id_middleware
from server.app.middleware.rate_limit import InMemoryRateLimiter
from server.app.sync.routes import router as sync_router
from server.app.utils.errors import install_error_handlers
from server.app.websocket.gateway import router as websocket_router
from server.app.workspaces.routes import router as workspaces_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create the DevSync Cloud FastAPI app."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.middleware("http")(InMemoryRateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds))
    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    install_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(workspaces_router)
    app.include_router(devices_router)
    app.include_router(sync_router)
    app.include_router(files_router)
    app.include_router(websocket_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Return service health."""
        return {"status": "ok", "environment": settings.environment, "version": settings.app_version}

    app.add_api_route("/v1/health", health, methods=["GET"], tags=["health"])

    logger.info("Created %s app in %s mode", settings.app_name, settings.environment)
    return app


app = create_app()


def main() -> int:
    """Run the server using uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run("server.app.main:app", host=settings.host, port=settings.port, reload=settings.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
