"""Bank holiday test fixtures.

Provides a sync Postgres session that operates against ``core.bank_holidays``.
Each test gets a clean slate: all rows inserted during the test are deleted in
teardown using a SAVEPOINT so the unique constraint is exercised exactly as in
production.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from shared.config import get_settings


@pytest.fixture()
def bh_db_session() -> Session:
    """Sync Postgres session targeting the real core.bank_holidays table.

    Wraps each test in a transaction that is rolled back on teardown so rows
    never persist between tests.
    """
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC, future=True)
    connection = engine.connect()
    # Begin an outer transaction we will roll back.
    trans = connection.begin()
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
        engine.dispose()
