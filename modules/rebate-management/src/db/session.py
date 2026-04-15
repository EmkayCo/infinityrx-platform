"""SQLAlchemy session factory for rebate-management module."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.tenant_context import install_tenant_loader

_engine = None
_SessionFactory = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get("REBATE_DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "REBATE_DATABASE_URL environment variable is required but not set. "
                "Set it to a valid PostgreSQL connection string."
            )
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=_get_engine(), autocommit=False, autoflush=False
        )
        install_tenant_loader(_SessionFactory)
    return _SessionFactory


def set_engine(engine) -> None:
    """Override engine — used by tests."""
    global _engine, _SessionFactory
    _engine = engine
    _SessionFactory = None


@contextmanager
def get_db_session() -> Generator[Session]:
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
