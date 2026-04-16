"""Re-export from shared.middleware.security_headers (canonical location).

M-02: deduplicated middleware -- no module-local copy allowed.
"""

from shared.middleware.security_headers import SecurityHeadersMiddleware  # noqa: F401

__all__ = ["SecurityHeadersMiddleware"]
