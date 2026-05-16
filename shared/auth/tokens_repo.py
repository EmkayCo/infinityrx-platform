"""Revoked-token repository abstraction.

Logout marks a token's ``jti`` as revoked so subsequent presentations fail.
Two implementations are provided:

* ``InMemoryRevokedTokenRepo`` — unit-test only. State is lost on restart,
  so production presentations of a previously-revoked token would succeed.
* ``RedisRevokedTokenRepo`` — production default. Keys are written as
  ``tenant:{tenant_id}:revoked:{jti}`` with a TTL equal to the token's
  remaining lifetime, so entries self-clean at token expiry and revocations
  survive process restarts.

Tenant isolation: every revocation key is prefixed with the caller's
``tenant_id`` so that a token revoked for Tenant A is invisible to Tenant B
(per .claude/rules/tenant-isolation.md — all Redis keys must carry
``tenant:{tenant_id}:`` prefix).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol


class RevokedTokenRepo(Protocol):
    def revoke(self, jti: uuid.UUID, tenant_id: uuid.UUID, expires_at: datetime) -> None: ...
    def is_revoked(self, jti: uuid.UUID, tenant_id: uuid.UUID) -> bool: ...
    def revoke_all_for_user(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None: ...


class InMemoryRevokedTokenRepo:
    """Thread-unsafe in-memory revocation store (tests/dev only)."""

    def __init__(self) -> None:
        # key: (tenant_id, jti) → expires_at
        self._revoked: dict[tuple[uuid.UUID, uuid.UUID], datetime] = {}
        # per-user JTI index: (tenant_id, user_id) → set[jti]
        self._user_jtis: dict[tuple[uuid.UUID, uuid.UUID], set[uuid.UUID]] = {}

    def revoke(self, jti: uuid.UUID, tenant_id: uuid.UUID, expires_at: datetime) -> None:
        self._revoked[(tenant_id, jti)] = expires_at

    def is_revoked(self, jti: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        exp = self._revoked.get((tenant_id, jti))
        if exp is None:
            return False
        if exp < datetime.now(tz=timezone.utc):
            # expired revocation entries can be cleaned lazily
            del self._revoked[(tenant_id, jti)]
            return False
        return True

    def revoke_all_for_user(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Revoke all JTIs tracked for ``user_id`` under ``tenant_id``.

        Only covers JTIs that were registered via the user-index (i.e. those
        added through ``_track_user_jti`` before revocation). In production use
        the caller should pass all known JTIs explicitly; this method is
        provided for the forced-logout / account-compromise use case where the
        caller holds the JTI set from the session store.
        """
        key = (tenant_id, user_id)
        for jti in list(self._user_jtis.get(key, set())):
            # Use a far-future expiry so the revocation outlives any plausible
            # token lifetime; the session store is the source of truth for
            # active JTIs.
            far_future = datetime.now(tz=timezone.utc).replace(year=9999)
            self._revoked[(tenant_id, jti)] = far_future
        self._user_jtis.pop(key, None)

    def _track_user_jti(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, jti: uuid.UUID
    ) -> None:
        """Register a JTI under its user so ``revoke_all_for_user`` finds it."""
        key = (tenant_id, user_id)
        self._user_jtis.setdefault(key, set()).add(jti)

    def clear(self) -> None:
        self._revoked.clear()
        self._user_jtis.clear()


class RedisRevokedTokenRepo:
    """Redis-backed revocation store — production default.

    Keys: ``tenant:{tenant_id}:revoked:{jti}``
    Value: empty byte string (existence is the signal).
    TTL: seconds until the token naturally expires (``exp - now``). Once the
         token is no longer valid under JWT rules, the revocation key no
         longer needs to exist, so Redis reclaims it automatically.

    Tenant isolation: every key is scoped to ``tenant:{tenant_id}:`` so that
    a JTI revoked for Tenant A is NOT visible to Tenant B — correct cross-
    tenant isolation is enforced by key-space segregation rather than by the
    caller remembering to filter (.claude/rules/tenant-isolation.md).

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

    revoke_all_for_user(): uses SCAN to find all keys matching
    ``tenant:{tenant_id}:revoked:user:{user_id}:*`` and issues a pipeline
    DEL. The user-index key ``tenant:{tenant_id}:user_jtis:{user_id}`` is a
    Redis SET of JTI strings so SCAN is not needed for the forced-logout path.
    """

    def __init__(
        self,
        redis: Any,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        """Args:
            redis: A ``redis.Redis`` client (sync).
            failure_threshold: Consecutive Redis failures before circuit opens.
            recovery_timeout: Seconds before the circuit allows a probe.
        """
        import logging  # noqa: PLC0415

        from shared.resilience.circuit_breaker import CircuitBreaker  # noqa: PLC0415

        self._redis = redis
        self._breaker = CircuitBreaker(
            "redis-revoked-token",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        self._log = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Internal key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _revoked_key(tenant_id: uuid.UUID, jti: uuid.UUID) -> str:
        """Redis key for a single revoked JTI.

        Pattern: ``tenant:{tenant_id}:revoked:{jti}``
        Matches .claude/rules/tenant-isolation.md — all Redis keys prefixed
        with ``tenant:{tenant_id}:``.
        """
        return f"tenant:{tenant_id}:revoked:{jti}"

    @staticmethod
    def _user_index_key(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
        """Redis SET key holding all active JTIs for a user.

        Pattern: ``tenant:{tenant_id}:user_jtis:{user_id}``
        """
        return f"tenant:{tenant_id}:user_jtis:{user_id}"

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    def revoke(self, jti: uuid.UUID, tenant_id: uuid.UUID, expires_at: datetime) -> None:
        from shared.resilience.circuit_breaker import CircuitOpenError  # noqa: PLC0415

        ttl = int((expires_at - datetime.now(tz=timezone.utc)).total_seconds())
        if ttl <= 0:
            # Token already expired — nothing to revoke.
            return
        key = self._revoked_key(tenant_id, jti)
        try:
            self._breaker.call(self._redis.setex, key, ttl, b"")
        except CircuitOpenError:
            self._log.warning(
                "revoked_token_store_circuit_open",
                extra={"svc_name": "redis-revoked-token", "jti": str(jti)},
            )
        except Exception:
            self._log.exception(
                "revoked_token_store_error",
                extra={"svc_name": "redis-revoked-token", "jti": str(jti)},
            )

    def is_revoked(self, jti: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        from shared.resilience.circuit_breaker import CircuitOpenError  # noqa: PLC0415

        key = self._revoked_key(tenant_id, jti)
        try:
            return bool(self._breaker.call(self._redis.exists, key))
        except CircuitOpenError:
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

    def revoke_all_for_user(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Revoke all JTIs tracked for ``user_id`` under ``tenant_id``.

        Reads the per-user JTI index set (``_user_index_key``), issues SETEX
        for each JTI with a far-future TTL (1 year) so they survive until the
        caller cleans up or they expire naturally, then deletes the index key.

        Fails-open on circuit open or Redis error — revocations that cannot
        be stored will self-expire via JWT ``exp`` claims.
        """
        from shared.resilience.circuit_breaker import CircuitOpenError  # noqa: PLC0415

        index_key = self._user_index_key(tenant_id, user_id)
        try:
            raw_jtis: set[bytes] = self._breaker.call(self._redis.smembers, index_key)
        except CircuitOpenError:
            self._log.warning(
                "revoked_token_user_index_circuit_open",
                extra={"svc_name": "redis-revoked-token", "auth_user_id": str(user_id)},
            )
            return
        except Exception:
            self._log.exception(
                "revoked_token_user_index_error",
                extra={"svc_name": "redis-revoked-token", "auth_user_id": str(user_id)},
            )
            return

        if not raw_jtis:
            return

        # Pipeline: SETEX each JTI key (1 year TTL) + DEL the index set.
        _ONE_YEAR_SECONDS = 365 * 24 * 3600
        try:
            pipe = self._redis.pipeline()
            for raw in raw_jtis:
                jti_str = raw.decode() if isinstance(raw, bytes) else raw
                jti = uuid.UUID(jti_str)
                pipe.setex(self._revoked_key(tenant_id, jti), _ONE_YEAR_SECONDS, b"")
            pipe.delete(index_key)
            self._breaker.call(pipe.execute)
        except CircuitOpenError:
            self._log.warning(
                "revoked_token_user_revoke_all_circuit_open",
                extra={"svc_name": "redis-revoked-token", "auth_user_id": str(user_id)},
            )
        except Exception:
            self._log.exception(
                "revoked_token_user_revoke_all_error",
                extra={"svc_name": "redis-revoked-token", "auth_user_id": str(user_id)},
            )

    def track_user_jti(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, jti: uuid.UUID, ttl: int
    ) -> None:
        """Add ``jti`` to the per-user index set so ``revoke_all_for_user`` finds it.

        The index key has the same TTL as the JTI so it self-cleans.
        Callers (e.g. login/token-issue path) should call this after minting
        each token. Fails-open on Redis error so login is never blocked.
        """
        from shared.resilience.circuit_breaker import CircuitOpenError  # noqa: PLC0415

        index_key = self._user_index_key(tenant_id, user_id)
        try:
            pipe = self._redis.pipeline()
            pipe.sadd(index_key, str(jti))
            pipe.expire(index_key, ttl)
            self._breaker.call(pipe.execute)
        except CircuitOpenError:
            self._log.warning(
                "revoked_token_track_jti_circuit_open",
                extra={"svc_name": "redis-revoked-token", "auth_user_id": str(user_id)},
            )
        except Exception:
            self._log.exception(
                "revoked_token_track_jti_error",
                extra={"svc_name": "redis-revoked-token", "auth_user_id": str(user_id)},
            )
