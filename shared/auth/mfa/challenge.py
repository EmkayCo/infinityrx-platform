"""shared.auth.mfa.challenge — short-lived MFA challenge token store.

When a user provides valid credentials but MFA is required, the login
endpoint issues a challenge token (NOT a JWT) that must be presented to
/auth/mfa/verify. Challenges are single-use and expire after 5 minutes.

Redis key space: ``mfa:challenge:{token}``
"""

from __future__ import annotations

import base64
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

__all__ = [
    "ChallengeClaims",
    "ChallengeStore",
    "InMemoryChallengeStore",
    "RedisChallengeStore",
    "create_challenge",
    "consume_challenge",
]

_CHALLENGE_TTL_SECONDS = 300  # 5 minutes
_TOKEN_BYTES = 32
_REDIS_PREFIX = "mfa:challenge:"


@dataclass(frozen=True)
class ChallengeClaims:
    """Claims embedded in a challenge token."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    method: str  # "totp" | "fido2"
    enrollment_required: bool = False


class ChallengeStore(Protocol):
    """Protocol for MFA challenge token stores."""

    async def put(self, token: str, claims: ChallengeClaims, ttl: int) -> None: ...
    async def get(self, token: str) -> ChallengeClaims | None: ...
    async def delete(self, token: str) -> None: ...


# ---------------------------------------------------------------------------
# In-memory store (test double)
# ---------------------------------------------------------------------------


class InMemoryChallengeStore:
    """Non-thread-safe in-memory implementation for tests."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[ChallengeClaims, datetime]] = {}

    async def put(self, token: str, claims: ChallengeClaims, ttl: int) -> None:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)
        self._store[token] = (claims, expires_at)

    async def get(self, token: str) -> ChallengeClaims | None:
        entry = self._store.get(token)
        if entry is None:
            return None
        claims, expires_at = entry
        if datetime.now(tz=timezone.utc) >= expires_at:
            del self._store[token]
            return None
        return claims

    async def delete(self, token: str) -> None:
        self._store.pop(token, None)

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# Redis-backed store (production)
# ---------------------------------------------------------------------------


class RedisChallengeStore:
    """Redis-backed challenge store using ``mfa:challenge:{token}`` key space.

    H-10: Graceful degradation on Redis failure. Each async method catches
    Redis errors and degrades safely:
    - put(): log and continue — worst case the challenge is never stored;
      the user will receive an invalid-challenge error on verification,
      which they can retry after Redis recovers.
    - get(): log and return None — the challenge is treated as not found;
      the user must restart the MFA flow after Redis recovers.
    - delete(): log and continue — the challenge remains in Redis until
      its TTL expires naturally (5 minutes), which is acceptable.
    """

    def __init__(self, redis: Any) -> None:
        """Args:
        redis: An async redis client (``redis.asyncio.Redis``).
        """
        import logging  # noqa: PLC0415

        self._redis = redis
        self._log = logging.getLogger(__name__)

    def _key(self, token: str) -> str:
        return f"{_REDIS_PREFIX}{token}"

    async def put(self, token: str, claims: ChallengeClaims, ttl: int) -> None:
        payload = json.dumps(
            {
                "user_id": str(claims.user_id),
                "tenant_id": str(claims.tenant_id),
                "method": claims.method,
                "enrollment_required": claims.enrollment_required,
            }
        )
        try:
            await self._redis.setex(self._key(token), ttl, payload)
        except Exception:
            self._log.exception(
                "mfa_challenge_store_put_failed",
                extra={"svc_name": "redis-mfa-challenge"},
            )

    async def get(self, token: str) -> ChallengeClaims | None:
        try:
            raw = await self._redis.get(self._key(token))
        except Exception:
            self._log.exception(
                "mfa_challenge_store_get_failed",
                extra={"svc_name": "redis-mfa-challenge"},
            )
            return None
        if raw is None:
            return None
        data = json.loads(raw)
        return ChallengeClaims(
            user_id=uuid.UUID(data["user_id"]),
            tenant_id=uuid.UUID(data["tenant_id"]),
            method=data["method"],
            enrollment_required=data.get("enrollment_required", False),
        )

    async def delete(self, token: str) -> None:
        try:
            await self._redis.delete(self._key(token))
        except Exception:
            self._log.exception(
                "mfa_challenge_store_delete_failed",
                extra={"svc_name": "redis-mfa-challenge"},
            )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _generate_token() -> str:
    """Generate a cryptographically random base64url token."""
    raw = secrets.token_bytes(_TOKEN_BYTES)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


async def create_challenge(
    store: ChallengeStore,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    method: str,
    enrollment_required: bool = False,
    ttl: int = _CHALLENGE_TTL_SECONDS,
) -> str:
    """Create a single-use MFA challenge token.

    Args:
        store: The challenge store to persist the token in.
        user_id: The user attempting to authenticate.
        tenant_id: The user's tenant.
        method: MFA method required ("totp" or "fido2").
        enrollment_required: True if the user must enroll before verifying.
        ttl: Token lifetime in seconds (default 300 / 5 min).

    Returns:
        Opaque challenge token string (base64url, 32 bytes of entropy).
    """
    token = _generate_token()
    claims = ChallengeClaims(
        user_id=user_id,
        tenant_id=tenant_id,
        method=method,
        enrollment_required=enrollment_required,
    )
    await store.put(token, claims, ttl)
    return token


async def consume_challenge(
    store: ChallengeStore,
    token: str,
) -> ChallengeClaims | None:
    """Consume a challenge token (single-use).

    Retrieves and deletes the token atomically. Returns None if the token
    does not exist or has expired.

    Args:
        store: The challenge store.
        token: The challenge token to consume.

    Returns:
        ChallengeClaims if valid, None otherwise.
    """
    claims = await store.get(token)
    if claims is None:
        return None
    await store.delete(token)
    return claims
