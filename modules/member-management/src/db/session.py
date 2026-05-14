"""Database session factory for member-management module.

Mirrors the prescriber-directory pattern: sync engine + sessionmaker created
on first use, bound by env var MEMBER_DB_URL. The fail-loud check prevents
silent fallback to localhost in production.

Wired into main.create_app() via app.dependency_overrides[] for each route's
local _get_db() placeholder. Without this wiring, member-mgmt routes raise
NotImplementedError at runtime (the failing-loud guard fires).
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.tenant_context import install_tenant_loader

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get("MEMBER_DB_URL")
        if not db_url:
            raise RuntimeError(
                "MEMBER_DB_URL environment variable is required but not set. "
                "Set it to a valid PostgreSQL connection string."
            )
        _engine = create_engine(db_url, pool_pre_ping=True, future=True)
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(), expire_on_commit=False, future=True
        )
        install_tenant_loader(_SessionLocal)
    return _SessionLocal


def set_engine(engine) -> None:
    """Override engine — used by tests. Resets session factory to rebuild
    with install_tenant_loader on the new engine."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = None


@contextmanager
def get_db_session() -> Iterator[Session]:
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def production_get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a real DB session.

    Wired into app.dependency_overrides[_get_db] for each route's
    local fail-loud placeholder in main.create_app().
    """
    with get_db_session() as session:
        yield session
