"""Re-export security headers middleware from shared middleware.

Modules import from here for consistency; the canonical implementation
lives in shared.middleware.security_headers.
"""

from shared.middleware import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
