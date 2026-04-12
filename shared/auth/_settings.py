"""Resolver for auth-related settings.

Runtime preference: ``shared.config.settings`` owned by Teammate 1. If that
module is not yet available in the current worktree (parallel development),
we fall back to environment variables so auth code still works for tests
and local development. During integration this shim will resolve to the
real settings object automatically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class _AuthSettings:
    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRES_MINUTES: int
    JWT_REFRESH_EXPIRES_MINUTES: int


def _load_from_env() -> _AuthSettings:
    secret = os.getenv("JWT_SECRET", "dev-insecure-secret-change-me-please-32chars!!")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters")
    return _AuthSettings(
        JWT_SECRET=secret,
        JWT_ALGORITHM=os.getenv("JWT_ALGORITHM", "HS256"),
        JWT_EXPIRES_MINUTES=int(os.getenv("JWT_EXPIRES_MINUTES", "60")),
        JWT_REFRESH_EXPIRES_MINUTES=int(os.getenv("JWT_REFRESH_EXPIRES_MINUTES", str(60 * 24 * 7))),
    )


def get_auth_settings() -> _AuthSettings:
    """Return auth settings.

    Prefers ``shared.config.settings`` if importable; otherwise reads env vars.
    Each call re-reads to make tests using monkeypatch predictable.
    """
    try:  # pragma: no cover - exercised at integration time
        from shared.config import settings as real  # type: ignore[attr-defined]

        return _AuthSettings(
            JWT_SECRET=real.JWT_SECRET,
            JWT_ALGORITHM=real.JWT_ALGORITHM,
            JWT_EXPIRES_MINUTES=int(real.JWT_EXPIRES_MINUTES),
            JWT_REFRESH_EXPIRES_MINUTES=int(
                getattr(real, "JWT_REFRESH_EXPIRES_MINUTES", 60 * 24 * 7)
            ),
        )
    except Exception:
        return _load_from_env()
