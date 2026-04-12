"""shared.auth — authentication utilities shared across all modules.

Contains:
- passwords: bcrypt hashing + verification
- jwt_tokens: access/refresh token creation and decoding
- exceptions: auth-specific exception hierarchy
- dependencies: FastAPI dependencies (get_current_user, require_roles, require_permissions)
- tokens_repo: revoked-token repository protocol + in-memory impl
"""

from shared.auth.exceptions import (
    AuthError,
    ExpiredTokenError,
    InvalidTokenError,
    WrongTokenTypeError,
)
from shared.auth.jwt_tokens import (
    TokenClaims,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
)
from shared.auth.passwords import hash_password, verify_password
from shared.auth.tokens_repo import InMemoryRevokedTokenRepo, RevokedTokenRepo

__all__ = [
    "AuthError",
    "ExpiredTokenError",
    "InMemoryRevokedTokenRepo",
    "InvalidTokenError",
    "RevokedTokenRepo",
    "TokenClaims",
    "WrongTokenTypeError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
    "verify_token_type",
]
