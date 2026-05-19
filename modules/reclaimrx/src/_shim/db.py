"""Minimal sync SQLAlchemy base + session for reclaimrx tests/dev.

Uses SQLite in-memory by default so tests run without PostgreSQL.

Tenant isolation: this module previously defined its own
``_current_tenant`` ContextVar which was disconnected from the
platform-wide ``shared.db.tenant_context.current_tenant_id``. Under
middleware that set the shared contextvar, reclaimrx code would see
``None`` — a silent isolation gap. As of P1 Item 4 of the emergency
wiring pass, ``tenant_context`` and ``current_tenant_id`` here are thin
re-exports of the shared primitives so reclaimrx services automatically
pick up whatever tenant the request middleware is running under.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from shared.db.tenant_context import (
    clear_tenant_context as _clear_shared_tenant,
    current_tenant_id as _shared_current_tenant_id,
    set_tenant_context as _set_shared_tenant,
)


class Base(DeclarativeBase):
    """Declarative base for reclaimrx models."""


_engine = None
_SessionLocal: sessionmaker | None = None  # type: ignore[type-arg]


def configure_engine(url: str = "sqlite:///:memory:") -> None:
    global _engine, _SessionLocal
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, future=True, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    # Wire the platform-wide tenant loader so reclaimrx models that
    # inherit ``TenantScopedMixin`` are auto-filtered by the shared
    # tenant contextvar. The loader's de-dupe flag makes multiple calls
    # safe across test iterations that reconfigure the engine.
    from shared.db.tenant_context import install_tenant_loader

    install_tenant_loader(_SessionLocal)


def get_engine():  # type: ignore[return]
    if _engine is None:
        configure_engine()
    return _engine


def get_sessionmaker() -> sessionmaker:  # type: ignore[type-arg]
    if _SessionLocal is None:
        configure_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_session() -> Iterator[Session]:
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def tenant_context(tenant_id: uuid.UUID) -> Iterator[None]:
    """Set the shared platform-wide tenant contextvar.

    Delegates to :mod:`shared.db.tenant_context` so that the reclaimrx
    module shares one source of truth with core-platform middleware.
    """
    token = _set_shared_tenant(tenant_id)
    try:
        yield
    finally:
        _clear_shared_tenant(token)


def current_tenant_id() -> uuid.UUID | None:
    """Return the current tenant UUID from the shared platform contextvar."""
    return _shared_current_tenant_id.get()


def create_all() -> None:
    Base.metadata.create_all(get_engine())


def drop_all() -> None:
    Base.metadata.drop_all(get_engine())


# ---------------------------------------------------------------------------
# Async engine (for PostgresIdempotencyStore and DLQ repository)
# ---------------------------------------------------------------------------

try:
    from sqlalchemy.ext.asyncio import create_async_engine
    _HAS_ASYNC = True
except ImportError:  # pragma: no cover
    _HAS_ASYNC = False  # type: ignore[assignment]

_async_engine = None


def get_async_engine_for_idempotency():
    """Return the module's async engine, built lazily from the SAME URL as the
    existing sync engine.

    Single source of truth: configure_engine(url) is the only place the URL is
    set; the async engine inherits it by reading get_engine().url. No parallel
    URL resolver.

    Used by PostgresIdempotencyStore and ReclaimRxDLQRepository. One instance
    per process.
    """
    global _async_engine
    if _async_engine is None:
        sync_url = str(get_engine().url)
        if sync_url.startswith("postgresql+psycopg2://"):
            async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("postgresql://"):
            async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("sqlite:///"):
            async_url = sync_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        elif sync_url.startswith("sqlite://"):
            # bare sqlite:// (in-memory) -- map to aiosqlite in-memory
            async_url = "sqlite+aiosqlite://"
        else:
            raise RuntimeError(
                f"Unsupported sync URL for async wrapping: {sync_url!r}. "
                "Add a branch here when introducing a new dialect."
            )
        _async_engine = create_async_engine(async_url, future=True)
    return _async_engine
