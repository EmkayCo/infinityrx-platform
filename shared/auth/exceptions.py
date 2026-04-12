"""Auth exception hierarchy."""

from __future__ import annotations


class AuthError(Exception):
    """Base class for authentication/authorization errors."""


class InvalidTokenError(AuthError):
    """Raised when a JWT is malformed, has an invalid signature, or missing claims."""


class ExpiredTokenError(AuthError):
    """Raised when a JWT has expired."""


class WrongTokenTypeError(AuthError):
    """Raised when a token of the wrong type is supplied (e.g. refresh used as access)."""
