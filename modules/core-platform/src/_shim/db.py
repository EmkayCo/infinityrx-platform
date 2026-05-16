"""Minimal sync SQLAlchemy base + session + tenant context for tests/dev.

Real implementation lives in shared/db/ (T1). This shim uses sync
SQLAlchemy against SQLite by default so tests run without Postgres.

NOTE (H-03 fix): _current_tenant is re-exported from shared.db.tenant_context
so that any existing imports of this shim's _current_tenant still work.
The canonical ContextVar lives in shared.db.tenant_context.current_tenant_id.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Re-export the canonical contextvar from shared so legacy imports don't break.
from shared.db.tenant_context import current_tenant_id as _current_tenant  # noqa: F401


class Base(DeclarativeBase):
    """Declarative base shared by all core-platform models."""


_engine = None
_SessionLocal: Optional[sessionmaker] = None


def configure_engine(url: str = "sqlite:///:memory:") -> None:
    global _engine, _SessionLocal
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    kw: dict = {}
    if url.startswith("sqlite"):
        # SQLite does not support schemas.  Map every schema used by core-platform
        # models (currently only "core") to None so ORM-generated SQL omits the
        # schema prefix and resolves against the flat SQLite table namespace.
        kw["execution_options"] = {"schema_translate_map": {"core": None}}
    _engine = create_engine(url, future=True, connect_args=connect_args, **kw)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def get_engine():
    if _engine is None:
        configure_engine()
    return _engine


def get_sessionmaker() -> sessionmaker:
    if _SessionLocal is None:
        configure_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_session() -> Session:
    """FastAPI dependency: yields a Session (caller must close)."""
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def tenant_context(tenant_id: uuid.UUID) -> Iterator[None]:
    from shared.db.tenant_context import current_tenant_id as _ctx_var

    token = _ctx_var.set(tenant_id)
    try:
        yield
    finally:
        _ctx_var.reset(token)


def current_tenant_id() -> Optional[uuid.UUID]:
    from shared.db.tenant_context import current_tenant_id as _ctx_var

    return _ctx_var.get()


def create_all() -> None:
    # The engine is configured with schema_translate_map={"core": None} for SQLite
    # (set in configure_engine), so SQLAlchemy translates away the schema= attribute
    # on both DDL (CREATE TABLE) and DML (SELECT/INSERT/UPDATE) for test engines.
    Base.metadata.create_all(get_engine())


def drop_all() -> None:
    Base.metadata.drop_all(get_engine())
