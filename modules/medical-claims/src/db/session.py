"""Sync session factory for medical-claims module.

All service-layer code in medical-claims uses sync SQLAlchemy Sessions.
This module provides a per-delivery session factory that commits on success
and rolls back on exception — matching the member-management pattern.

MEDICAL_CLAIMS_DB_URL must be set in production (fail-fast on missing env var).
Tests inject their own engine via set_engine() and pass the resulting
session factory to wire_consumers() directly.
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
        db_url = os.environ.get("MEDICAL_CLAIMS_DB_URL")
        if not db_url:
            raise RuntimeError(
                "MEDICAL_CLAIMS_DB_URL environment variable is required but not set. "
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
    """Override engine — used by tests. Resets session factory so it rebuilds
    with install_tenant_loader applied to the new engine."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = None


@contextmanager
def get_db_session() -> Iterator[Session]:
    """Context manager yielding a sync Session. Commits on success, rolls back on exception."""
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
