"""Tests for the async engine and session factory."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db import engine as engine_mod
from shared.db import session as session_mod
from shared.db.engine import dispose_engine, get_engine
from shared.db.session import get_sessionmaker, reset_sessionmaker, transaction


@pytest.fixture(autouse=True)
def _reset_engine_state():
    engine_mod._engine = None  # type: ignore[attr-defined]
    reset_sessionmaker()
    yield
    engine_mod._engine = None  # type: ignore[attr-defined]
    reset_sessionmaker()


def test_get_engine_is_singleton() -> None:
    e1 = get_engine()
    e2 = get_engine()
    assert isinstance(e1, AsyncEngine)
    assert e1 is e2


def test_engine_pool_parameters() -> None:
    e = get_engine()
    pool = e.pool
    assert pool.size() == 20
    # _max_overflow is private API but stable across SA 2.x
    assert pool._max_overflow == 10  # type: ignore[attr-defined]
    assert pool._recycle == 1800  # type: ignore[attr-defined]
    assert pool._pre_ping is True  # type: ignore[attr-defined]


def test_get_sessionmaker_is_singleton() -> None:
    a = get_sessionmaker()
    b = get_sessionmaker()
    assert a is b


async def test_dispose_engine_clears_singleton() -> None:
    get_engine()
    await dispose_engine()
    assert engine_mod._engine is None  # type: ignore[attr-defined]


async def test_dispose_engine_is_noop_when_already_disposed() -> None:
    await dispose_engine()
    assert engine_mod._engine is None  # type: ignore[attr-defined]


async def test_transaction_helper_commits(pg_sessionmaker) -> None:
    async with pg_sessionmaker() as session:
        async with transaction(session):
            await session.execute(text("SELECT 1"))
        assert not session.in_transaction()


async def test_transaction_helper_nested(pg_sessionmaker) -> None:
    async with pg_sessionmaker() as session:
        async with transaction(session):
            async with transaction(session):
                await session.execute(text("SELECT 1"))


async def test_get_session_dependency_yields_session() -> None:
    # Exercise the FastAPI dependency by iterating the async generator.
    agen = session_mod.get_session()
    sess = await agen.__anext__()
    try:
        assert sess is not None
    finally:
        with pytest.raises(StopAsyncIteration):
            await agen.__anext__()
