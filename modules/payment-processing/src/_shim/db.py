"""Minimal sync SQLAlchemy base + session for payment-processing tests/dev.

Tenant isolation: ``configure_engine`` wires the platform-wide tenant
loader onto the generated ``Session`` class. Models that inherit
``TenantScopedMixin`` are then auto-scoped to the active tenant
contextvar. Payment-processing's own models do not yet inherit the mixin
— tracked as a follow-up task.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from shared.db.tenant_context import install_tenant_loader


class Base(DeclarativeBase):
    """Declarative base shared by all payment-processing models."""


_engine = None
_SessionLocal: sessionmaker | None = None  # type: ignore[type-arg]


def configure_engine(url: str = "sqlite:///:memory:") -> None:
    global _engine, _SessionLocal
    if url == "sqlite:///:memory:":
        # Use StaticPool so all connections share the same in-memory database
        from sqlalchemy.pool import StaticPool
        _engine = create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, future=True, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
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


@contextmanager
def session_scope() -> Iterator[Session]:
    maker = get_sessionmaker()
    session: Session = maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    maker = get_sessionmaker()
    session: Session = maker()
    try:
        yield session
    finally:
        session.close()
