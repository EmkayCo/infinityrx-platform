"""Revoked-token repository abstraction.

Logout marks a token's ``jti`` as revoked so subsequent presentations fail.
An in-memory implementation is provided for tests and local dev. Production
integration will swap in a Redis-backed implementation with TTL equal to the
token's remaining lifetime.

Linked task: modules/core-platform/tasks/todo.md :: swap-revoked-repo-redis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol


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
