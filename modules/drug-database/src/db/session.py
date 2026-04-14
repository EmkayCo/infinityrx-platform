"""SQLAlchemy session factory for drug-database module."""
from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.tenant_context import install_tenant_loader

_DATABASE_URL = os.environ.get(
    "DRUG_DB_DATABASE_URL",
    "postgresql+psycopg2://drug_db:drug_db@localhost:5432/infinityrx_drug_db",
)

_engine = None
_SessionFactory = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
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
