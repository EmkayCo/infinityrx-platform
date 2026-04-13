"""Revoked-token repository abstraction.

Logout marks a token's ``jti`` as revoked so subsequent presentations fail.
Two implementations are provided:

* ``InMemoryRevokedTokenRepo`` — unit-test only. State is lost on restart,
  so production presentations of a previously-revoked token would succeed.
* ``RedisRevokedTokenRepo`` — production default. Keys are written as
  ``revoked:jti:{jti}`` with a TTL equal to the token's remaining lifetime,
  so entries self-clean at token expiry and revocations survive process
  restarts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

_KEY_PREFIX = "revoked:jti:"


class RevokedTokenRepo(Protocol):
    def revoke(self, jti: uuid.UUID, expires_at: datetime) -> None: ...
    def is_revoked(self, jti: uuid.UUID) -> bool: ...


class InMemoryRevokedTokenRepo:
    """Thread-unsafe in-memory revocation store (tests/dev only)."""

    def __init__(self) -> None:
        self._revoked: dict[uuid.UUID, datetime] = {}

    def revoke(self, jti: uuid.UUID, expires_at: datetime) -> None:
        self._revoked[jti] = expires_at

    def is_revoked(self, jti: uuid.UUID) -> bool:
        exp = self._revoked.get(jti)
        if exp is None:
            return False
        if exp < datetime.now(tz=timezone.utc):
            # expired revocation entries can be cleaned lazily
            del self._revoked[jti]
            return False
        return True

    def clear(self) -> None:
        self._revoked.clear()


class RedisRevokedTokenRepo:
    """Redis-backed revocation store — production default.

    Keys: ``revoked:jti:{jti}``
    Value: empty byte string (existence is the signal).
    TTL: seconds until the token naturally expires (``exp - now``). Once the
         token is no longer valid under JWT rules, the revocation key no
         longer needs to exist, so Redis reclaims it automatically.

    A revocation request for an already-expired token is a no-op: SETEX with
    ttl<=0 would be rejected, so we skip the write entirely. The token is
    already unusable by JWT verification.
    """

    def __init__(self, redis: Any, *, key_prefix: str = _KEY_PREFIX) -> None:
        """Args:
            redis: A ``redis.Redis`` client (sync).
            key_prefix: Override for multi-tenant Redis deployments. Defaults
                to ``revoked:jti:``.
        """
        self._redis = redis
        self._prefix = key_prefix

    def _key(self, jti: uuid.UUID) -> str:
        return f"{self._prefix}{jti}"

    def revoke(self, jti: uuid.UUID, expires_at: datetime) -> None:
        ttl = int((expires_at - datetime.now(tz=timezone.utc)).total_seconds())
        if ttl <= 0:
            # Token already expired — nothing to revoke.
            return
        self._redis.setex(self._key(jti), ttl, b"")

    def is_revoked(self, jti: uuid.UUID) -> bool:
        return bool(self._redis.exists(self._key(jti)))
