"""Minimal sync SQLAlchemy base + session + tenant context for tests/dev.

Real implementation lives in shared/db/ (T1). This shim uses sync
SQLAlchemy against SQLite by default so tests run without Postgres.
"""
from __future__ import annotations

import contextvars
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_current_tenant: contextvars.ContextVar[Optional[uuid.UUID]] = contextvars.ContextVar(
    "current_tenant", default=None
)


class Base(DeclarativeBase):
    """Declarative base shared by all core-platform models."""


_engine = None
_SessionLocal: Optional[sessionmaker] = None


def configure_engine(url: str = "sqlite:///:memory:") -> None:
    global _engine, _SessionLocal
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, future=True, connect_args=connect_args)
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
    token = _current_tenant.set(tenant_id)
    try:
        yield
    finally:
        _current_tenant.reset(token)


def current_tenant_id() -> Optional[uuid.UUID]:
    return _current_tenant.get()


def create_all() -> None:
    Base.metadata.create_all(get_engine())


def drop_all() -> None:
    Base.metadata.drop_all(get_engine())
