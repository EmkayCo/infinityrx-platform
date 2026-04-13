"""SQLAlchemy session factory for billing module."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_DATABASE_URL = os.environ.get(
    "BILLING_DATABASE_URL",
    "postgresql+psycopg2://billing:billing@localhost:5432/infinityrx_billing",
)

_engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
_SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


@contextmanager
def get_db_session() -> Generator[Session]:
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
