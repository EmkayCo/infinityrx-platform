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

    H-10: Wrapped with a CircuitBreaker so Redis downtime causes graceful
    degradation rather than cascading auth failures.
    - revoke(): fail-open on circuit open (log; do not crash — token will
      expire naturally via JWT exp, which is the last-resort guard).
    - is_revoked(): fail-open on circuit open (returns False — safe because
      JWT expiry remains enforced; a brief window of non-revocation is
      preferable to bringing down auth entirely).
    """

    def __init__(
        self,
        redis: Any,
        *,
        key_prefix: str = _KEY_PREFIX,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        """Args:
            redis: A ``redis.Redis`` client (sync).
            key_prefix: Override for multi-tenant Redis deployments.
            failure_threshold: Consecutive Redis failures before circuit opens.
            recovery_timeout: Seconds before the circuit allows a probe.
        """
        import logging  # noqa: PLC0415

        from shared.resilience.circuit_breaker import CircuitBreaker  # noqa: PLC0415

        self._redis = redis
        self._prefix = key_prefix
        self._breaker = CircuitBreaker(
            "redis-revoked-token",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        self._log = logging.getLogger(__name__)

    def _key(self, jti: uuid.UUID) -> str:
        return f"{self._prefix}{jti}"

    def revoke(self, jti: uuid.UUID, expires_at: datetime) -> None:
        from shared.resilience.circuit_breaker import CircuitOpenError  # noqa: PLC0415

        ttl = int((expires_at - datetime.now(tz=timezone.utc)).total_seconds())
        if ttl <= 0:
            # Token already expired — nothing to revoke.
            return
        try:
            self._breaker.call(self._redis.setex, self._key(jti), ttl, b"")
        except CircuitOpenError:
            # Redis is down — log and continue. The JWT exp claim still guards
            # against the token being usable after expiry.
            self._log.warning(
                "revoked_token_store_circuit_open",
                extra={"svc_name": "redis-revoked-token", "jti": str(jti)},
            )
        except Exception:
            self._log.exception(
                "revoked_token_store_error",
                extra={"svc_name": "redis-revoked-token", "jti": str(jti)},
            )

    def is_revoked(self, jti: uuid.UUID) -> bool:
        from shared.resilience.circuit_breaker import CircuitOpenError  # noqa: PLC0415

        try:
            return bool(self._breaker.call(self._redis.exists, self._key(jti)))
        except CircuitOpenError:
            # Fail-open: assume not revoked so auth continues to function.
            # The JWT exp claim still rejects expired tokens.
            self._log.warning(
                "revoked_token_check_circuit_open_fail_open",
                extra={"svc_name": "redis-revoked-token", "jti": str(jti)},
            )
            return False
        except Exception:
            self._log.exception(
                "revoked_token_check_error",
                extra={"svc_name": "redis-revoked-token", "jti": str(jti)},
            )
            return False
