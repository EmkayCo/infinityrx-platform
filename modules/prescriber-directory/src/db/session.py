"""Database session factory for prescriber-directory module.

Uses SQLite in tests (schema patched to None) and PostgreSQL in production.
All sessions are sync for simplicity; the FastAPI routes use Depends(get_db).

IMPORTANT: install_tenant_loader is called on every new session factory so
that tenant context criteria are applied to every query (CR-09/tenant-isolation.md).
The PRESCRIBER_DB_URL environment variable MUST be set in production — there is no
hardcoded fallback (M-16/GROUP 8 hardening).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.tenant_context import install_tenant_loader


_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get("PRESCRIBER_DB_URL")
        if not db_url:
            raise RuntimeError(
                "PRESCRIBER_DB_URL environment variable is required but not set. "
                "Set it to a valid PostgreSQL connection string."
            )
        _engine = create_engine(db_url, pool_pre_ping=True, future=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), expire_on_commit=False, future=True)
        install_tenant_loader(_SessionLocal)  # CR-09: apply tenant criteria to every query
    return _SessionLocal


def set_engine(engine) -> None:
    """Override engine — used by tests. Resets the session factory so _get_session_factory()
    will rebuild it with install_tenant_loader applied to the new engine."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = None  # force rebuild via _get_session_factory() on next call


@contextmanager
def get_db_session() -> Iterator[Session]:
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
