"""Security headers + rate limit middleware for pharmacy-directory."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'",
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

_DEFAULT_RATE_LIMIT = 200  # req/min
_RATE_WINDOW_SECONDS = 60


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        response.headers["X-Request-ID"] = str(uuid.uuid4())
        return response


class _Bucket:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: int) -> None:
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self, capacity: int) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill = int(elapsed / _RATE_WINDOW_SECONDS * capacity)
        if refill > 0:
            self.tokens = min(capacity, self.tokens + refill)
            self.last_refill = now
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = _DEFAULT_RATE_LIMIT) -> None:
        super().__init__(app)
        self._limit = limit
        self._buckets: dict[str, _Bucket] = {}

    def _key(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        key = self._key(request)
        bucket = self._buckets.setdefault(key, _Bucket(self._limit))
        if not bucket.consume(self._limit):
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"}},
                headers={"Retry-After": str(_RATE_WINDOW_SECONDS)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._limit)
        response.headers["X-RateLimit-Remaining"] = str(bucket.tokens)
        return response
