"""Shared fixtures for DB integration tests.

Every integration test uses a *per-test* Postgres schema so tests can run
in parallel without stepping on each other, and so we don't need to burn a
fresh container for every test. The schema is dropped on teardown.

We reuse the local docker-compose Postgres instance (the same one the
preflight validator checks) rather than spinning up testcontainers — this
is an order of magnitude faster and is fine because the schema is isolated.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.config import get_settings
from shared.db.base import Base
from shared.db.models import core as _core_models  # noqa: F401  ensure metadata populated
from shared.db.tenant_context import install_tenant_loader


@pytest.fixture(scope="session")
def database_url() -> str:
    return get_settings().DATABASE_URL


@pytest_asyncio.fixture()
async def pg_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """Async engine pinned to a unique schema per test."""
    schema = f"t_{uuid.uuid4().hex[:10]}"
    engine = create_async_engine(database_url, future=True)

    # Force every new connection to use the test schema as its search_path,
    # so the model declarations (which say `schema="core"`) land in our
    # private copy. We remap by creating an alias schema `core` via a
    # per-connection SET search_path — simpler: create a dedicated schema
    # named `core` inside the test database is impossible (already exists).
    # Instead we create the schema and rely on a schema-translate map.
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    translated = engine.execution_options(schema_translate_map={"core": schema})

    async with translated.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield translated
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest_asyncio.fixture()
async def pg_sessionmaker(
    pg_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    sm = async_sessionmaker(bind=pg_engine, expire_on_commit=False, class_=AsyncSession)
    install_tenant_loader(sm)
    yield sm
