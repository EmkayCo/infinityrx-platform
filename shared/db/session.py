"""Async session factory, FastAPI dependency, and transaction helper.

All database work MUST go through `get_session()` (or `get_sessionmaker()`
for one-off scripts) so that the tenant-isolation loader criteria attached
in :mod:`shared.db.tenant_context` are applied to every query.

`transaction()` is a reusable async context manager that opens a SAVEPOINT
(or the outermost BEGIN if none is active) and commits / rolls back as a
single unit. This is the building block for "Cannot lose data on crash —
transaction boundaries everywhere" from CLAUDE.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from shared.db.engine import get_engine
from shared.db.tenant_context import install_tenant_loader

_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
        install_tenant_loader(_sessionmaker)
    return _sessionmaker


def reset_sessionmaker() -> None:
    """Drop the cached session factory. Tests use this after swapping engines."""
    global _sessionmaker
    _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an AsyncSession with automatic close."""
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Open a transaction (outer BEGIN or nested SAVEPOINT) around a block."""
    if session.in_transaction():
        async with session.begin_nested():
            yield session
    else:
        async with session.begin():
            yield session
