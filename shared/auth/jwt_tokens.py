"""JWT token creation, decoding, and validation.

Tokens are signed with HS256 (configurable via settings). Two token types
are supported:

- ``access`` (short-lived): carries ``sub``, ``tid``, ``roles``
- ``refresh`` (long-lived): carries only ``sub``

Every token has a unique ``jti`` (so it can be revoked individually) and
``iat``/``exp`` timestamps.

All decode failures raise a domain exception (``InvalidTokenError`` or
``ExpiredTokenError``) — callers should never see a raw PyJWT exception.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from shared.auth._settings import get_auth_settings
from shared.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    WrongTokenTypeError,
)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


@dataclass(frozen=True)
class TokenClaims:
    sub: uuid.UUID
    typ: str
    jti: uuid.UUID
    iat: datetime
    exp: datetime
    tenant_id: uuid.UUID | None
    roles: tuple[str, ...]

    @property
    def user_id(self) -> uuid.UUID:
        return self.sub


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _encode(payload: dict[str, Any]) -> str:
    s = get_auth_settings()
    return jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)


def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    roles: list[str],
) -> str:
    """Create a short-lived access token.

    Claims: sub, tid, roles, typ=access, iat, exp, jti.
    """
    if not isinstance(user_id, uuid.UUID) or not isinstance(tenant_id, uuid.UUID):
        raise ValueError("user_id and tenant_id must be UUIDs")
    s = get_auth_settings()
    now = _now()
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "roles": list(roles),
        "typ": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.JWT_EXPIRES_MINUTES)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a long-lived refresh token bound to a user."""
    if not isinstance(user_id, uuid.UUID):
        raise ValueError("user_id must be a UUID")
    s = get_auth_settings()
    now = _now()
    payload = {
        "sub": str(user_id),
        "typ": TOKEN_TYPE_REFRESH,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.JWT_REFRESH_EXPIRES_MINUTES)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def decode_token(token: str) -> TokenClaims:
    """Decode and validate a JWT, returning strongly-typed claims.

    Raises:
        ExpiredTokenError: token's exp is in the past.
        InvalidTokenError: signature mismatch, malformed token, or missing claims.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("token must be a non-empty string")
    s = get_auth_settings()
    try:
        raw = jwt.decode(
            token,
            s.JWT_SECRET,
            algorithms=[s.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "typ", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError(f"invalid token: {exc}") from exc

    try:
        sub = uuid.UUID(raw["sub"])
        jti = uuid.UUID(raw["jti"])
        typ = str(raw["typ"])
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError(f"malformed token claims: {exc}") from exc

    if typ not in (TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH):
        raise InvalidTokenError(f"unknown token type: {typ}")

    tid_raw = raw.get("tid")
    try:
        tenant_id = uuid.UUID(tid_raw) if tid_raw else None
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError(f"malformed tid claim: {exc}") from exc

    roles_raw = raw.get("roles") or []
    if not isinstance(roles_raw, list):
        raise InvalidTokenError("roles claim must be a list")

    return TokenClaims(
        sub=sub,
        typ=typ,
        jti=jti,
        iat=datetime.fromtimestamp(int(raw["iat"]), tz=timezone.utc),
        exp=datetime.fromtimestamp(int(raw["exp"]), tz=timezone.utc),
        tenant_id=tenant_id,
        roles=tuple(str(r) for r in roles_raw),
    )


def verify_token_type(claims: TokenClaims, expected_type: str) -> None:
    """Raise WrongTokenTypeError if *claims.typ* != *expected_type*."""
    if claims.typ != expected_type:
        raise WrongTokenTypeError(
            f"expected token type '{expected_type}', got '{claims.typ}'"
        )
