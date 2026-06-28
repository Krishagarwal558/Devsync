"""Basic in-memory rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.responses import JSONResponse


class InMemoryRateLimiter:
    """Sliding-window per-client rate limiter for single-process MVP deployments."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Apply rate limit to HTTP requests."""
        if request.url.path in {"/health", "/v1/health"}:
            return await call_next(request)
        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = self._requests[client_key]
        while bucket and now - bucket[0] > self._window_seconds:
            bucket.popleft()
        if len(bucket) >= self._max_requests:
            request_id = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=429,
                headers={"X-Request-ID": request_id or ""},
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Please wait and try again.",
                        "request_id": request_id,
                    }
                },
            )
        bucket.append(now)
        return await call_next(request)
