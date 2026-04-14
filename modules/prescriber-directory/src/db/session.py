"""Database session factory for prescriber-directory module.

Uses SQLite in tests (schema patched to None) and PostgreSQL in production.
All sessions are sync for simplicity; the FastAPI routes use Depends(get_db).
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        import os
        db_url = os.environ.get(
            "PRESCRIBER_DB_URL",
            "postgresql+psycopg2://localhost/prescriber_directory",
        )
        _engine = create_engine(db_url, future=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def set_engine(engine) -> None:
    """Override engine — used by tests."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


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
