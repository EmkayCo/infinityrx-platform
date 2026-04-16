"""Rate limiting middleware for the EBV/EBI/RTBC module.

Simple in-memory rate limiter. In production, backed by Redis
with tenant-scoped keys.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_minute: int = 600
    burst_size: int = 100


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: RateLimitConfig | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - 60.0

        bucket = self._buckets[client_ip]
        self._buckets[client_ip] = [t for t in bucket if t > window_start]

        if len(self._buckets[client_ip]) >= self.config.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"}},
                headers={"Retry-After": "60"},
            )

        self._buckets[client_ip].append(now)
        return await call_next(request)
