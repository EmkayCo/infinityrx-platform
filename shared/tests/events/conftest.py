"""Fixtures for event bus tests including PostgreSQL and RabbitMQ integration."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "postgres: requires a live PostgreSQL instance")
    config.addinivalue_line("markers", "rabbitmq: requires a live RabbitMQ instance")


def _pg_url() -> str:
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://infinityrx:infinityrx_dev@localhost:5432/infinityrx",
    )


@pytest.fixture
def pg_engine() -> AsyncEngine:
    """Function-scoped async SQLAlchemy engine pointing at local Postgres.

    Tests marked @pytest.mark.postgres are skipped automatically if the
    database is not reachable.  Function-scoped to avoid asyncpg
    'another operation is in progress' errors when tests share an engine.
    """
    return create_async_engine(_pg_url(), echo=False)
