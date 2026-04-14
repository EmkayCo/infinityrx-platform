"""Backward-compatible re-export from shared.middleware.security_headers.

The canonical implementation lives in shared/middleware/security_headers.py.
This module re-exports everything so existing imports in this module
(and tests that import from here) continue to work without changes.
"""

from shared.middleware.security_headers import SecurityHeadersMiddleware  # noqa: F401

__all__ = ["SecurityHeadersMiddleware"]
