"""Re-export shared rate limiter for module use."""

from shared.middleware import RateLimitConfig, RateLimitMiddleware

__all__ = ["RateLimitConfig", "RateLimitMiddleware"]
