"""Token bucket rate limiter middleware.

Supports per-tenant, per-user, and per-endpoint rate limits.
Uses an in-memory token bucket for local development and testing.
Production should swap to Redis-backed buckets.

Rate limit headers added to every response:
- X-RateLimit-Limit
- X-RateLimit-Remaining
- X-RateLimit-Reset (seconds until bucket refill)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

__all__ = [
    "RateLimitConfig",
    "TokenBucket",
    "InMemoryBucketStore",
    "RateLimitMiddleware",
]


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate limit configuration."""

    tenant_rpm: int = 1000  # requests per minute per tenant
    user_rpm: int = 100  # requests per minute per user
    burst_multiplier: float = 1.5  # allow bursts up to this * rpm


@dataclass
class TokenBucket:
    """Token bucket implementation."""

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def consume(self, n: int = 1) -> tuple[bool, float, float]:
        """Try to consume n tokens.

        Returns:
            (allowed, remaining, seconds_until_refill)
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= n:
            self.tokens -= n
            seconds_to_full = (self.capacity - self.tokens) / self.refill_rate if self.refill_rate > 0 else 0
            return True, self.tokens, seconds_to_full
        else:
            wait = (n - self.tokens) / self.refill_rate if self.refill_rate > 0 else 60
            return False, 0.0, wait


class InMemoryBucketStore:
    """In-memory bucket store keyed by string identifiers."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def get_or_create(self, key: str, capacity: float, refill_rate: float) -> TokenBucket:
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(capacity=capacity, refill_rate=refill_rate)
        return self._buckets[key]

    def clear(self) -> None:
        self._buckets.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware applying token-bucket rate limiting.

    Extracts tenant_id and user_id from request state (set by auth middleware).
    Skips rate limiting for health check endpoints.
    """

    def __init__(
        self,
        app: object,
        config: RateLimitConfig | None = None,
        store: InMemoryBucketStore | None = None,
    ) -> None:
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.store = store or InMemoryBucketStore()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip health endpoints
        if request.url.path.startswith("/health") or request.url.path.startswith("/api/v1/health"):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None) if hasattr(request, "state") else None
        user_id = getattr(request.state, "user_id", None) if hasattr(request, "state") else None

        # Tenant-level rate limit
        if tenant_id:
            capacity = self.config.tenant_rpm * self.config.burst_multiplier
            refill_rate = self.config.tenant_rpm / 60.0
            bucket = self.store.get_or_create(f"tenant:{tenant_id}", capacity, refill_rate)
            allowed, remaining, reset = bucket.consume()
            if not allowed:
                return self._too_many_requests(
                    int(capacity), remaining, reset, "tenant"
                )

        # User-level rate limit
        if user_id:
            capacity = self.config.user_rpm * self.config.burst_multiplier
            refill_rate = self.config.user_rpm / 60.0
            bucket = self.store.get_or_create(f"user:{user_id}", capacity, refill_rate)
            allowed, remaining, reset = bucket.consume()
            if not allowed:
                return self._too_many_requests(
                    int(capacity), remaining, reset, "user"
                )

        response = await call_next(request)

        # Add rate limit headers (user-level if available, else tenant)
        if user_id:
            bucket = self.store.get_or_create(
                f"user:{user_id}",
                self.config.user_rpm * self.config.burst_multiplier,
                self.config.user_rpm / 60.0,
            )
            _, remaining, reset = bucket.consume(0)
            response.headers["X-RateLimit-Limit"] = str(self.config.user_rpm)
            response.headers["X-RateLimit-Remaining"] = str(int(remaining))
            response.headers["X-RateLimit-Reset"] = str(int(reset))
        elif tenant_id:
            bucket = self.store.get_or_create(
                f"tenant:{tenant_id}",
                self.config.tenant_rpm * self.config.burst_multiplier,
                self.config.tenant_rpm / 60.0,
            )
            _, remaining, reset = bucket.consume(0)
            response.headers["X-RateLimit-Limit"] = str(self.config.tenant_rpm)
            response.headers["X-RateLimit-Remaining"] = str(int(remaining))
            response.headers["X-RateLimit-Reset"] = str(int(reset))

        return response

    @staticmethod
    def _too_many_requests(
        limit: int, remaining: float, reset: float, scope: str
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded ({scope}). Try again in {int(reset)} seconds.",
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset)),
                "Retry-After": str(int(reset)),
            },
        )
