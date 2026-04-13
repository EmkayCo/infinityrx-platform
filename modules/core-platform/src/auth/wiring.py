"""Wire the shared auth dependencies to the core-platform ORM models.

The core-platform module owns the canonical user store, so it must
supply the ``UserLoader`` used by ``shared.auth.dependencies``. This
module provides:

* ``build_user_loader(SessionLocal)`` — factory that opens a short-lived
  session per call and materialises a ``shared.auth.CurrentUser``
* ``configure_core_auth(SessionLocal, repo)`` — one-shot wiring used by
  tests and application composition
"""

from __future__ import annotations

import os
import uuid
from typing import Callable

from sqlalchemy.orm import sessionmaker

from shared.auth.dependencies import CurrentUser, configure_auth
from shared.auth.tokens_repo import (
    InMemoryRevokedTokenRepo,
    RedisRevokedTokenRepo,
    RevokedTokenRepo,
)
from src.auth.service import load_authenticated


def build_user_loader(
    SessionLocal: sessionmaker,
) -> Callable[[uuid.UUID], CurrentUser | None]:
    def loader(user_id: uuid.UUID) -> CurrentUser | None:
        with SessionLocal() as session:
            auth = load_authenticated(session, user_id)
            if auth is None:
                return None
            user = auth.user
            return CurrentUser(
                id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                status=user.status,
                roles=tuple(auth.roles),
                permissions=tuple(auth.permissions),
            )

    return loader


def _default_revoked_repo() -> RevokedTokenRepo:
    """Pick the production default.

    If ``REDIS_URL`` is set, connect and return ``RedisRevokedTokenRepo`` so
    revocations survive process restarts (HIPAA availability / auth-control
    integrity requirement). Otherwise fall back to the in-memory repo — only
    appropriate for tests and local dev without Redis.
    """
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return InMemoryRevokedTokenRepo()
    import redis  # imported lazily so the import cost is paid only when needed

    client = redis.Redis.from_url(redis_url, decode_responses=False)
    return RedisRevokedTokenRepo(client)


def configure_core_auth(
    SessionLocal: sessionmaker,
    repo: RevokedTokenRepo | None = None,
) -> RevokedTokenRepo:
    repo = repo or _default_revoked_repo()
    configure_auth(build_user_loader(SessionLocal), repo)
    return repo
