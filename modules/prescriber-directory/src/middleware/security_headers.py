"""Security headers middleware for prescriber-directory service."""

from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_STATIC_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'",
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        if not hasattr(request, "state"):
            request.state = type("State", (), {})()  # pragma: no cover
        request.state.request_id = request_id

        response = await call_next(request)

        for header, value in _STATIC_HEADERS.items():
            response.headers[header] = value
        response.headers["X-Request-ID"] = request_id

        return response
