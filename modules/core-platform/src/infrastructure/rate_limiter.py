"""Backward-compatible re-export from shared.middleware.rate_limiter.

The canonical implementation lives in shared/middleware/rate_limiter.py.
This module re-exports everything so existing imports in this module
(and tests that import from here) continue to work without changes.
"""

from shared.middleware.rate_limiter import (  # noqa: F401
    InMemoryBucketStore,
    RateLimitConfig,
    RateLimitMiddleware,
    TokenBucket,
)

__all__ = [
    "RateLimitConfig",
    "TokenBucket",
    "InMemoryBucketStore",
    "RateLimitMiddleware",
]
