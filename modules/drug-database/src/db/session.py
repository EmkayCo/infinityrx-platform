"""SQLAlchemy session factory for drug-database module.

M-16: No hardcoded DB URL fallback. DRUG_DB_DATABASE_URL must be set
in the environment. A clear RuntimeError is raised at first use if absent.
"""
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
        db_url = os.environ.get("DRUG_DB_DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "DRUG_DB_DATABASE_URL environment variable is required but not set. "
                "Set it to a valid PostgreSQL connection string."
            )
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
        install_tenant_loader(_SessionFactory)
    return _SessionFactory


def reset_session_factory() -> None:
    """Drop cached engine/factory. Call in tests after overriding engine."""
    global _engine, _SessionFactory
    _engine = None
    _SessionFactory = None


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
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
