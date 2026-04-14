"""Token bucket rate limiter middleware for drug-database service."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

__all__ = ["RateLimitConfig", "TokenBucket", "InMemoryBucketStore", "RateLimitMiddleware"]


@dataclass(frozen=True)
class RateLimitConfig:
    tenant_rpm: int = 1000
    user_rpm: int = 100
    burst_multiplier: float = 1.5


@dataclass
class TokenBucket:
    capacity: float
    refill_rate: float
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def consume(self, n: int = 1) -> tuple[bool, float, float]:
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
    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def get_or_create(self, key: str, capacity: float, refill_rate: float) -> TokenBucket:
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(capacity=capacity, refill_rate=refill_rate)
        return self._buckets[key]

    def clear(self) -> None:
        self._buckets.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, config: RateLimitConfig | None = None, store: InMemoryBucketStore | None = None) -> None:
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.store = store or InMemoryBucketStore()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in ("/api/v1/drugs/health", "/health"):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None) if hasattr(request, "state") else None

        if tenant_id:
            capacity = self.config.tenant_rpm * self.config.burst_multiplier
            refill_rate = self.config.tenant_rpm / 60.0
            bucket = self.store.get_or_create(f"tenant:{tenant_id}", capacity, refill_rate)
            allowed, remaining, reset = bucket.consume()
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Rate limit exceeded. Retry in {int(reset)}s."},
                    headers={"Retry-After": str(int(reset))},
                )

        response = await call_next(request)
        return response
