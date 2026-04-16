"""Re-export rate limiter from shared middleware.

Modules import from here for consistency; the canonical implementation
lives in shared.middleware.rate_limiter.
"""

from shared.middleware import RateLimitConfig, RateLimitMiddleware

__all__ = ["RateLimitConfig", "RateLimitMiddleware"]
